import webview
import json
import os
import shutil
from flask import Flask, send_from_directory
import webbrowser
import subprocess
import os
import helper
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)
window = None

# 暴露给JS的API
class Api:
    def __init__(self):
        self.project_path = ""  # 项目文件夹路径
        self.base_json_path = ""  # 基础JSON路径
        self.base_folder_path = ""  # 基础文件夹路径
        self.plans_folder_path = ""  # 方案文件夹路径
        self.current_plan_path = ""  # 当前选择的方案路径
        self.export_path = ""  # 导出路径
        self.data = []  # 所有模组数据
        self.selected_mods = []  # 当前选中的模组名称列表
        self.test_command = ""  # 测试游戏命令
        self.mask_plan_path = ""  # 遮掩方案路径
        self.mask_mode = ""  # 遮掩模式：include(包含) 或 exclude(排除)
        self.pending_replacements = {}  # 保存待替换的mod信息，格式: {新mod名称: (新mod信息, 新mod路径, 旧mod名称)}

    def select_project_folder(self):
        """选择项目文件夹"""
        path = window.create_file_dialog(webview.FOLDER_DIALOG)
        if not path or not path[0]:
            return {"status": "error", "message": "未选择文件夹"}
        
        self.project_path = path[0]
        
        # 创建必要的文件夹和文件
        self.base_folder_path = os.path.join(self.project_path, "base")
        self.plans_folder_path = os.path.join(self.project_path, "plans")
        self.base_json_path = os.path.join(self.project_path, "base.json")
        
        # 确保文件夹存在
        os.makedirs(self.base_folder_path, exist_ok=True)
        os.makedirs(self.plans_folder_path, exist_ok=True)
        
        # 如果base.json不存在，创建一个空的json文件
        if not os.path.exists(self.base_json_path):
            with open(self.base_json_path, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=4)
        
        # 加载基础配置
        result = self.load_base_config()
        # 添加项目路径到结果中
        result["project_path"] = self.project_path
        return result
    
    def load_base_config(self):
        """加载基础配置"""
        try:
            if not self.base_json_path or not os.path.exists(self.base_json_path):
                return {"status": "error", "message": "基础配置文件不存在"}
                
            with open(self.base_json_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            
            # 验证base文件夹中是否存在所有模组文件
            mods_to_remove = []
            for item in self.data:
                mod_path = os.path.join(self.base_folder_path, item['name'])
                if not os.path.exists(mod_path):
                    mods_to_remove.append(item)
            
            # 从数据中移除不存在的mod
            if mods_to_remove:
                # 收集被删除的mod名称
                removed_mod_names = [item['name'] for item in mods_to_remove]
                
                for item in mods_to_remove:
                    self.data.remove(item)
                # 保存更新后的基础配置
                with open(self.base_json_path, 'w', encoding='utf-8') as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=4)
                
                result = {
                    "status": "warning", 
                    "message": f"已移除{len(mods_to_remove)}个不存在的模组：\n{', '.join(removed_mod_names)}", 
                    "data": self._get_processed_data()
                }
            else:
                # 清空当前选中列表
                self.selected_mods = []
                result = {"status": "success", "data": self._get_processed_data()}
            
            # 如果之前选择了方案，自动加载该方案
            if self.current_plan_path and os.path.exists(self.current_plan_path):
                plan_name = os.path.basename(self.current_plan_path)[:-5]  # 去掉.json后缀
                plan_result = self.load_plan(plan_name)
                if plan_result["status"] == "success":
                    result["message"] = f"已自动加载方案: {plan_name}"
            
            return result
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def get_available_plans(self):
        """获取可用的方案列表"""
        if not self.plans_folder_path or not os.path.exists(self.plans_folder_path):
            return {"status": "error", "message": "方案文件夹不存在"}
        
        try:
            plans = []
            for file in os.listdir(self.plans_folder_path):
                if file.endswith('.json'):
                    plans.append(file[:-5])  # 移除.json后缀
            
            return {"status": "success", "data": plans}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def load_plan(self, plan_name):
        """加载指定方案"""
        if not plan_name:
            self.current_plan_path = ""
            self.selected_mods = []
            return {"status": "success", "message": "已清除当前方案", "data": self._get_processed_data()}
        
        plan_path = os.path.join(self.plans_folder_path, f"{plan_name}.json")
        if not os.path.exists(plan_path):
            return {"status": "error", "message": f"方案 {plan_name} 不存在"}
        
        try:
            with open(plan_path, 'r', encoding='utf-8') as f:
                plan_data = json.load(f)
            
            # 更新当前方案路径和选中列表
            self.current_plan_path = plan_path
            self.selected_mods = [item["name"] for item in plan_data]
            
            return {"status": "success", "data": self._get_processed_data()}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def select_export_folder(self):
        """选择导出文件夹"""
        path = window.create_file_dialog(webview.FOLDER_DIALOG)
        if not path or not path[0]:
            return ""
        
        self.export_path = path[0]
        return self.export_path
    
    def toggle_mod_selection(self, mod_name):
        """切换模组选择状态"""
        try:
            if mod_name in self.selected_mods:
                self.selected_mods.remove(mod_name)
            else:
                self.selected_mods.append(mod_name)
            
            return {"status": "success", "data": self._get_processed_data()}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def save_current_plan(self, plan_name=None):
        """保存当前方案"""
        try:
            # 确定保存路径
            save_path = self.current_plan_path
            
            # 如果提供了新方案名，或当前没有加载方案，则创建新方案路径
            if not save_path or plan_name:
                # 确保方案名存在
                if not plan_name:
                    return {"status": "error", "message": "未指定方案名称，且当前未加载方案"}
                
                save_path = os.path.join(self.plans_folder_path, f"{plan_name}.json")
                self.current_plan_path = save_path
            
            # 创建方案数据
            plan_data = []
            for item in self.data:
                if item["name"] in self.selected_mods:
                    plan_data.append(item)
            
            # 保存方案数据
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(plan_data, f, ensure_ascii=False, indent=4)
            
            return {
                "status": "success", 
                "message": "方案已保存", 
                "plan_name": os.path.basename(save_path)[:-5],
                "data": self._get_processed_data()
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def get_test_command(self):
        """获取测试游戏命令"""
        return self.test_command
    
    def save_test_command(self, command):
        """保存测试游戏命令"""
        self.test_command = command
        return {'status': 'success', 'message': '已保存测试命令'}
    
    def run_test_command(self):
        """运行测试游戏命令"""
        try:
            if not self.test_command:
                return {'status': 'error', 'message': '请先设置测试命令'}
            
            if not self.project_path:
                return {'status': 'error', 'message': '请先选择项目文件夹'}
            
            # 切换到项目目录并运行命令
            current_dir = os.getcwd()
            os.chdir(self.project_path)
            
            # 在新进程中运行命令，不阻塞主线程
            import subprocess
            subprocess.Popen(self.test_command, shell=True)
            
            # 切回原目录
            os.chdir(current_dir)
            
            return {'status': 'success', 'message': '已启动游戏'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def export_selected_mods(self):
        """导出选中的模组"""
        try:
            if not self.export_path:
                return {'status': 'error', 'message': '请先选择导出路径'}
            
            if not self.project_path:
                return {'status': 'error', 'message': '请先选择项目文件夹'}
            
            # 获取当前选中的模组名称
            selected_mod_names = self.selected_mods
            
            if not selected_mod_names:
                return {'status': 'error', 'message': '未选中任何模组'}
            
            # 清空目标文件夹中的所有文件
            if os.path.exists(self.export_path):
                for item in os.listdir(self.export_path):
                    item_path = os.path.join(self.export_path, item)
                    if os.path.isfile(item_path):
                        os.remove(item_path)
            else:
                os.makedirs(self.export_path, exist_ok=True)
            
            # 复制选中的模组到导出路径
            for mod_name in selected_mod_names:
                for item in self.data:
                    if item['name'] == mod_name:
                        source_path = os.path.join(self.base_folder_path, mod_name)
                        if os.path.exists(source_path):
                            shutil.copy(source_path, os.path.join(self.export_path, mod_name))
                        break
            
            return {'status': 'success', 'message': f'已成功导出 {len(selected_mod_names)} 个模组'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def process_auto_check(self, name, detail_comment=False):
        """自动检测并补充模组信息
        
        Args:
            name: 模组名称
            detail_comment: 是否使用详细评论模式
        """
        for i in self.data:
            if i['name'] == name:
                def run_step(field, updateMsg, func, failMsg, *args, **kwargs):
                    if not i.get(field, "").strip():
                        window.evaluate_js(f"update_loading_content({json.dumps(name)}, {json.dumps(updateMsg)})")
                        if not func(i, *args, **kwargs):
                            raise Exception(failMsg)

                try:
                    run_step("url", "Searching curseforge url", helper.process_get_url, "Failed to find curseforge url")
                    if (not i.get("desc", "").strip()) or (i.get("desc", "").strip() == ""):
                        window.evaluate_js(f"update_loading_content({json.dumps(name)}, 'Fetching mod info')")
                        if not helper.process_get_text(i):
                            raise Exception("Failed to fetch mod info")
                        window.evaluate_js(f"update_loading_content({json.dumps(name)}, 'Suammaring mod info')")
                        if not helper.process_get_summary(i):
                            raise Exception("Failed to summary info")
                    run_step("mcmod_url", "Fetching mcmod url", helper.process_get_url_mcmod, "Failed to fetch mcmod url")
                    run_step("label_name", "Fetching mod label", helper.process_get_label, "Failed to fetch mod label")
                    
                    # 添加获取评论和风险分析的步骤
                    if not i.get("mcmod_comment_text", "").strip() or "【Mod风险分析】" not in i.get("comment", ""):
                        detail_text = "详细模式" if detail_comment else ""
                        window.evaluate_js(f"update_loading_content({json.dumps(name)}, {json.dumps('Fetching mcmod comments and analyzing risks ' + detail_text)})")
                        helper.process_get_comment(i, detail=detail_comment)
                    
                    window.evaluate_js(f"update_loading_content({json.dumps(name)}, 'Done.')")
                except Exception as e:
                    # 将错误消息转换为字符串并使用JSON序列化处理特殊字符
                    error_msg = str(e)
                    window.evaluate_js(f"update_loading_content({json.dumps(name)}, {json.dumps(error_msg)})")

                time.sleep(1)
                break

        with open(self.base_json_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)

        return {'status': 'success', 'data': name}
                
    def process_add_mod(self, name, path, detail_comment=False):
        print(name, path)
        current_mod = {'name': name}
        
        def update_and_run(step_msg, func, err_msg, *args, **kwargs):
            window.evaluate_js(f"update_loading_content({json.dumps(name)}, {json.dumps(step_msg)})")
            if not func(current_mod, *args, **kwargs):
                raise Exception(err_msg)
        
        try:
            update_and_run("Searching curseforge url", helper.process_get_url, "Failed to find curseforge url")
        except Exception as e:
            window.evaluate_js(f"update_loading_content({json.dumps(name)}, {json.dumps(str(e))})")
            return
        
        try:
            update_and_run("Fetching mod info", helper.process_get_text, "Failed to fetch mod info")
            update_and_run("Suammaring mod info", helper.process_get_summary, "Failed to summary info")
        except Exception as e:
            window.evaluate_js(f"update_loading_content({json.dumps(name)}, {json.dumps(str(e))})")
            time.sleep(1)
        
        try:
            update_and_run("Fetching mcmod url", helper.process_get_url_mcmod, "Failed to fetch mcmod url")
            update_and_run("Fetching mod label", helper.process_get_label, "Failed to fetch mod label")
        except Exception as e:
            window.evaluate_js(f"update_loading_content({json.dumps(name)}, {json.dumps(str(e))})")
            time.sleep(1)
        
        # 尝试获取MCMod评论并分析风险
        try:
            detail_text = "详细模式" if detail_comment else ""
            update_and_run(f"Fetching mcmod comments and analyzing risks {detail_text}", 
                           helper.process_get_comment, 
                           "Failed to fetch comments", 
                           detail=detail_comment)
        except Exception as e:
            window.evaluate_js(f"update_loading_content({json.dumps(name)}, {json.dumps(str(e))})")
            time.sleep(1)
        
        # 检查是否存在重复mod
        duplicate_found = False
        old_mod_name = None
        
        for mod in self.data:
            if "url" in mod and "url" in current_mod and mod.get("url") == current_mod.get("url"):
                duplicate_found = True
                old_mod_name = mod.get("name")
                break
        
        if duplicate_found:
            window.evaluate_js(f"update_loading_content({json.dumps(name)}, 'Find duplicate mod')")
            # 保存替换信息，以便后续替换操作
            self.pending_replacements[name] = (current_mod, path, old_mod_name)
        else:
            window.evaluate_js(f"update_loading_content({json.dumps(name)}, 'Done.')")
            shutil.copy(path, os.path.join(self.base_folder_path, name))
            self.data.append(current_mod)

    def manual_add_file(self):
        try:
            # 检查是否已选择项目文件夹
            if not self.project_path or not os.path.exists(self.project_path):
                return {'status': 'error', 'message': '请先选择项目文件夹'}
                
            file_path = window.create_file_dialog(webview.OPEN_DIALOG)
            if not file_path or not file_path[0]:
                return {'status': 'error', 'message': '未选择文件'}
                
            name = os.path.basename(file_path[0])
            shutil.copy(file_path[0], os.path.join(self.base_folder_path, name))
            self.data.append({'name': name})
                
            with open(self.base_json_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)

            return {'status': 'success', 'data': self._get_processed_data()}
        except Exception as e:
            print(e)
            return {'status': 'error', 'message': str(e)}
        
    def add_file(self):
        try:
            if not self.project_path or not os.path.exists(self.project_path):
                return {'status': 'error', 'message': '请先选择项目文件夹'}
            
            # 如果在遮掩模式下，先提醒用户
            is_masked = self.mask_plan_path and os.path.exists(self.mask_plan_path)
            if is_masked:
                # 返回特殊状态，让前端显示确认对话框
                return {
                    'status': 'mask_warning', 
                    'message': '当前处于遮掩模式，添加的mod将同时添加到遮掩方案中。是否继续？'
                }
                
            return self._add_file_impl()
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def confirm_add_file(self):
        """确认在遮掩模式下添加文件"""
        return self._add_file_impl()
    
    def _add_file_impl(self, detail_comment=False):
        """添加文件的实际实现
        
        Args:
            detail_comment: 是否获取详细评论
        """
        try:
            # 清理待替换列表
            self.pending_replacements = {}
            
            file_paths = window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True)
            
            if not file_paths:
                return {'status': 'error', 'message': '未选择文件'}
                
            files = [(path, os.path.basename(path)) for path in file_paths]
            if len(files) == 0:
                return {'status': 'failed', 'message': '未选择文件'}
            
            for i in files:
                window.evaluate_js(f"update_loading_content({json.dumps(i[1])}, 'Pending')")
                

            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(self.process_add_mod, i[1], i[0], detail_comment): i for i in files}
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        print(e)
                
            with open(self.base_json_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
            
            # 如果在遮掩模式下，同步更新遮掩方案
            if self.mask_plan_path and os.path.exists(self.mask_plan_path):
                self._update_mask_with_new_mods([i[1] for i in files])
                self._reload_mask()

            return {'status': 'success', 'data': self._get_processed_data()}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def _update_mask_with_new_mods(self, mod_names):
        """将新添加的mod更新到遮掩方案中"""
        try:
            if not self.mask_plan_path or not os.path.exists(self.mask_plan_path):
                return False
                
            # 读取遮掩方案数据
            with open(self.mask_plan_path, 'r', encoding='utf-8') as f:
                mask_data = json.load(f)
            
            # 获取遮掩方案中已有的mod名称
            mask_mod_names = [item['name'] for item in mask_data if 'name' in item]
            
            # 添加新mod到遮掩方案
            for mod_name in mod_names:
                # 检查mod是否已在遮掩方案中
                if mod_name not in mask_mod_names:
                    # 从self.data中查找完整的mod信息
                    for item in self.data:
                        if item['name'] == mod_name:
                            mask_data.append(item)
                            break
            
            # 保存更新后的遮掩方案
            with open(self.mask_plan_path, 'w', encoding='utf-8') as f:
                json.dump(mask_data, f, ensure_ascii=False, indent=4)
                
            return True
        except Exception as e:
            print(f"更新遮掩方案时出错: {str(e)}")
            return False

    def start_game(self, command):
        try:
            result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        except Exception as e:
            print("Exception:", e)

    def open_url(self, url):
        webbrowser.open_new_tab(url)
        return True

    def delete_item(self, item_name):
        """删除指定的模组项目"""
        try:
            found = False
            for item in self.data:
                if "name" in item.keys() and item['name'] == item_name:
                    found = True
                    self.data.remove(item)
                    mod_path = os.path.join(self.base_folder_path, item_name)
                    if os.path.exists(mod_path):
                        os.remove(mod_path)
                    
                    # 如果该mod在选中列表中，也移除它
                    if item_name in self.selected_mods:
                        self.selected_mods.remove(item_name)
                    break
            
            if not found:
                return {'status': 'error', 'message': f'未找到模组：{item_name}'}

            # 保存更新后的数据
            with open(self.base_json_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
            
            # 从所有方案中移除该mod
            if os.path.exists(self.plans_folder_path):
                for plan_file in os.listdir(self.plans_folder_path):
                    if plan_file.endswith('.json'):
                        plan_path = os.path.join(self.plans_folder_path, plan_file)
                        try:
                            with open(plan_path, 'r', encoding='utf-8') as f:
                                plan_data = json.load(f)
                            
                            # 从方案中移除mod
                            plan_updated = False
                            plan_data_new = [item for item in plan_data if item.get('name') != item_name]
                            if len(plan_data_new) != len(plan_data):
                                plan_updated = True
                            
                            # 只有当方案有更新时才写入文件
                            if plan_updated:
                                with open(plan_path, 'w', encoding='utf-8') as f:
                                    json.dump(plan_data_new, f, ensure_ascii=False, indent=4)
                        except Exception as e:
                            print(f"更新方案文件 {plan_file} 时出错: {str(e)}")
            
            # 如果启用了遮掩方案，重新加载遮掩
            if self.mask_plan_path and os.path.exists(self.mask_plan_path):
                self._reload_mask()

            return {'status': 'success', 'data': self._get_processed_data(), 'message': f'已删除模组：{item_name}'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def update_item(self, item_name, tag, new_value):
        try:
            # 查找对应 item
            updated = False
            for item in self.data:
                if item['name'] == item_name:
                    # 如果不存在该 tag，则添加；否则更新其值
                    item[tag] = new_value
                    updated = True
                    break
                    
            if not updated:
                return {'status': 'error', 'message': f'未找到模组：{item_name}'}
                
            # 将更新后的数据写回 JSON 文件
            with open(self.base_json_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
                
            # 同步更新所有方案中的条目
            if os.path.exists(self.plans_folder_path):
                for plan_file in os.listdir(self.plans_folder_path):
                    if plan_file.endswith('.json'):
                        plan_path = os.path.join(self.plans_folder_path, plan_file)
                        try:
                            with open(plan_path, 'r', encoding='utf-8') as f:
                                plan_data = json.load(f)
                            
                            # 遍历方案中的所有条目
                            plan_updated = False
                            for plan_item in plan_data:
                                if "name" in plan_item and plan_item["name"] == item_name:
                                    plan_item[tag] = new_value
                                    plan_updated = True
                            
                            # 只有当方案有更新时才写入文件
                            if plan_updated:
                                with open(plan_path, 'w', encoding='utf-8') as f:
                                    json.dump(plan_data, f, ensure_ascii=False, indent=4)
                        except Exception as e:
                            print(f"更新方案文件 {plan_file} 时出错: {str(e)}")
            
            # 如果启用了遮掩方案，重新加载遮掩
            if os.path.exists(self.mask_plan_path):
                self._reload_mask()

            return {'status': 'success', 'data': self._get_processed_data()}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def _get_processed_data(self):
        """处理数据，添加选择状态，并根据遮掩方案过滤数据"""
        processed_data = [{
            **item,
            'selected': item['name'] in self.selected_mods
        } for item in self.data]
        
        # 如果没有设置遮掩方案，返回所有数据
        if not self.mask_plan_path or not os.path.exists(self.mask_plan_path):
            return processed_data
        
        try:
            # 读取遮掩方案数据
            with open(self.mask_plan_path, 'r', encoding='utf-8') as f:
                mask_data = json.load(f)
            
            # 获取遮掩方案中的mod名称列表
            mask_mod_names = [item['name'] for item in mask_data if 'name' in item]
            
            # 根据遮掩模式过滤数据
            if self.mask_mode == "include":
                # 只显示遮掩方案中存在的mod
                return [item for item in processed_data if item['name'] in mask_mod_names]
            elif self.mask_mode == "exclude":
                # 不显示遮掩方案中存在的mod
                return [item for item in processed_data if item['name'] not in mask_mod_names]
            
            # 如果遮掩模式不正确，返回所有数据
            return processed_data
        except Exception as e:
            print(f"应用遮掩方案时出错: {str(e)}")
            return processed_data

    def close_window(self):
        """关闭窗口"""
        window.destroy()
        exit()  # 直接终止程序
        return {"status": "success"}

    def replace_mod(self, old_mod_name):
        """替换指定的模组文件，并更新相关JSON条目"""
        try:
            if not self.project_path or not os.path.exists(self.project_path):
                return {'status': 'error', 'message': '请先选择项目文件夹'}
                
            file_paths = window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=('Mod 文件 (*.jar)',))
            
            if not file_paths or not file_paths[0]:
                return {'status': 'error', 'message': '未选择文件'}
            
            new_mod_path = file_paths[0]
            new_mod_name = os.path.basename(new_mod_path)
            
            # 检查原模组是否存在
            old_mod_found = False
            old_mod_index = -1
            for i, item in enumerate(self.data):
                if "name" in item and item["name"] == old_mod_name:
                    old_mod_found = True
                    old_mod_index = i
                    break
            
            if not old_mod_found:
                return {'status': 'error', 'message': f'未找到原模组：{old_mod_name}'}
            
            # 替换文件
            old_mod_path = os.path.join(self.base_folder_path, old_mod_name)
            new_target_path = os.path.join(self.base_folder_path, new_mod_name)
            
            # 如果原文件存在，删除它
            if os.path.exists(old_mod_path):
                os.remove(old_mod_path)
            
            # 复制新文件到目标位置
            shutil.copy2(new_mod_path, new_target_path)
            
            # 更新 base.json 中的条目
            self.data[old_mod_index]["name"] = new_mod_name
            
            # 保存更新后的数据
            with open(self.base_json_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
            
            # 更新所有方案文件中的条目
            for plan_file in os.listdir(self.plans_folder_path):
                if plan_file.endswith('.json'):
                    plan_path = os.path.join(self.plans_folder_path, plan_file)
                    try:
                        with open(plan_path, 'r', encoding='utf-8') as f:
                            plan_data = json.load(f)
                        
                        # 遍历方案中的所有条目
                        plan_updated = False
                        for item in plan_data:
                            if "name" in item and item["name"] == old_mod_name:
                                item["name"] = new_mod_name
                                plan_updated = True
                        
                        # 只有当方案有更新时才写入文件
                        if plan_updated:
                            with open(plan_path, 'w', encoding='utf-8') as f:
                                json.dump(plan_data, f, ensure_ascii=False, indent=4)
                    except Exception as e:
                        print(f"更新方案文件 {plan_file} 时出错: {str(e)}")
            
            # 如果旧模组在选中列表中，更新选中列表
            if old_mod_name in self.selected_mods:
                self.selected_mods.remove(old_mod_name)
                self.selected_mods.append(new_mod_name)
            
            # 如果启用了遮掩方案，重新加载遮掩
            if self.mask_plan_path and os.path.exists(self.mask_plan_path):
                self._reload_mask()
            
            return {'status': 'success', 'data': self._get_processed_data(), 'message': f'已替换模组：{old_mod_name} -> {new_mod_name}'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def create_new_plan(self, plan_name):
        """创建一个新的空白方案"""
        try:
            if not plan_name or not plan_name.strip():
                return {"status": "error", "message": "方案名称不能为空"}
                
            if not self.plans_folder_path or not os.path.exists(self.plans_folder_path):
                return {"status": "error", "message": "方案文件夹不存在"}
                
            plan_path = os.path.join(self.plans_folder_path, f"{plan_name}.json")
            
            # 检查方案是否已存在
            if os.path.exists(plan_path):
                return {"status": "error", "message": f"方案 {plan_name} 已存在"}
                
            # 创建空方案文件
            with open(plan_path, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=4)
                
            # 更新当前方案路径和选中列表
            self.current_plan_path = plan_path
            self.selected_mods = []
            
            return {
                "status": "success", 
                "message": f"已创建新方案: {plan_name}", 
                "data": self._get_processed_data()
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def set_mask_plan(self, plan_name, mask_mode):
        """设置遮掩方案和模式"""
        try:
            if not plan_name:
                # 清除遮掩
                self.mask_plan_path = ""
                self.mask_mode = ""
                return {"status": "success", "message": "已清除遮掩方案", "data": self._get_processed_data()}
            
            if mask_mode not in ["include", "exclude"]:
                return {"status": "error", "message": "遮掩模式必须是'include'或'exclude'"}
            
            plan_path = os.path.join(self.plans_folder_path, f"{plan_name}.json")
            if not os.path.exists(plan_path):
                return {"status": "error", "message": f"方案 {plan_name} 不存在"}
            
            self.mask_plan_path = plan_path
            self.mask_mode = mask_mode
            
            return {"status": "success", "message": f"已设置遮掩方案: {plan_name} (模式: {mask_mode})", "data": self._get_processed_data()}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def _reload_mask(self):
        """重新加载遮掩方案"""
        if not self.mask_plan_path or not os.path.exists(self.mask_plan_path):
            return
        
        try:
            # 重新加载遮掩方案数据
            with open(self.mask_plan_path, 'r', encoding='utf-8') as f:
                mask_data = json.load(f)
            
            # 更新处理后的数据
            self._get_processed_data()
            
            return True
        except Exception as e:
            print(f"重新加载遮掩方案时出错: {str(e)}")
            return False

    def replace_duplicate_mod(self, mod_name):
        """替换重复的mod"""
        try:
            # 检查mod是否在待替换列表中
            if mod_name not in self.pending_replacements:
                return {'status': 'error', 'message': f'未找到待替换的mod: {mod_name}'}
            
            # 获取替换信息
            new_mod_info, new_mod_path, old_mod_name = self.pending_replacements[mod_name]
            
            # 查找旧mod在数据中的索引
            old_mod_index = -1
            for i, item in enumerate(self.data):
                if item.get('name') == old_mod_name:
                    old_mod_index = i
                    break
            
            if old_mod_index == -1:
                return {'status': 'error', 'message': f'未找到原mod: {old_mod_name}'}
            
            # 替换文件
            old_mod_path = os.path.join(self.base_folder_path, old_mod_name)
            new_target_path = os.path.join(self.base_folder_path, mod_name)
            
            # 如果原文件存在，删除它
            if os.path.exists(old_mod_path):
                os.remove(old_mod_path)
            
            # 复制新文件到目标位置
            shutil.copy2(new_mod_path, new_target_path)
            
            # 更新数据中的信息
            # 保留旧mod的一些信息，如selected状态
            is_selected = old_mod_name in self.selected_mods
            
            # 替换数据中的mod信息
            self.data[old_mod_index] = new_mod_info
            
            # 如果旧mod在选中列表中，更新选中列表
            if is_selected:
                self.selected_mods.remove(old_mod_name)
                self.selected_mods.append(mod_name)
            
            # 更新方案文件中的mod信息
            if os.path.exists(self.plans_folder_path):
                for plan_file in os.listdir(self.plans_folder_path):
                    if plan_file.endswith('.json'):
                        plan_path = os.path.join(self.plans_folder_path, plan_file)
                        try:
                            with open(plan_path, 'r', encoding='utf-8') as f:
                                plan_data = json.load(f)
                            
                            # 遍历方案中的所有条目
                            plan_updated = False
                            for i, plan_item in enumerate(plan_data):
                                if plan_item.get('name') == old_mod_name:
                                    plan_data[i] = new_mod_info
                                    plan_updated = True
                            
                            # 只有当方案有更新时才写入文件
                            if plan_updated:
                                with open(plan_path, 'w', encoding='utf-8') as f:
                                    json.dump(plan_data, f, ensure_ascii=False, indent=4)
                        except Exception as e:
                            print(f"更新方案文件 {plan_file} 时出错: {str(e)}")
            
            # 保存更新后的数据
            with open(self.base_json_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
            
            # 如果启用了遮掩方案，重新加载遮掩
            if self.mask_plan_path and os.path.exists(self.mask_plan_path):
                self._reload_mask()
            
            # 从待替换列表中移除
            del self.pending_replacements[mod_name]
            
            return {'status': 'success', 'message': f'已替换mod: {old_mod_name} -> {mod_name}'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def clear_pending_replacements(self):
        """清理待替换列表"""
        self.pending_replacements = {}
        return {'status': 'success'}

    def add_file_detail(self):
        """使用详细评论模式添加文件"""
        try:
            if not self.project_path or not os.path.exists(self.project_path):
                return {'status': 'error', 'message': '请先选择项目文件夹'}
            
            # 如果在遮掩模式下，先提醒用户
            is_masked = self.mask_plan_path and os.path.exists(self.mask_plan_path)
            if is_masked:
                # 返回特殊状态，让前端显示确认对话框
                return {
                    'status': 'mask_warning_detail', 
                    'message': '当前处于遮掩模式且启用详细评论，添加的mod将同时添加到遮掩方案中。是否继续？'
                }
                
            return self._add_file_impl(detail_comment=True)
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def confirm_add_file_detail(self):
        """确认在遮掩模式下使用详细评论模式添加文件"""
        return self._add_file_impl(detail_comment=True)

    def auto_check_detail(self, name):
        """使用详细评论模式进行自动检查"""
        return self.process_auto_check(name, detail_comment=True)

@app.route('/')
def index():
    return send_from_directory('web', 'index.html')

@app.route('/<path:filename>')
def serve_file(filename):
    return send_from_directory('web', filename)

def start_server():
    app.run(host='127.0.0.1', port=5000, threaded=True)

if __name__ == '__main__':
    import threading
    import sys
    
    try:
        t = threading.Thread(target=start_server)
        t.daemon = True
        t.start()
        
        api = Api()
        window = webview.create_window('MOD管理器', 'http://127.0.0.1:5000/', js_api=api)
        webview.start()
    except Exception as e:
        print(f"程序出错: {e}")
        sys.exit(1)