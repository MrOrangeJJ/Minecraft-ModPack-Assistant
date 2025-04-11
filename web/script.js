let allItems = [];
let currentEditingItem = null;
let right_search_value = "";
let left_search_value = "";
let processing_list = {};
let currentPlan = "";
let projectPath = "";
let exportPath = "";
let isMaskMode = false;
let currentMaskPlan = "";
let currentMaskMode = "include";
let runningTasks = {};
let taskIdCounter = 0;

// 初始化：在页面加载完成后自动请求选择项目文件夹
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(async function() {
        const result = await pywebview.api.select_project_folder();
        if (result.status === 'error' && result.message === "未选择文件夹") {
            // 用户取消了选择，直接关闭窗口
            pywebview.api.close_window();
            return;
        }
        
        if (result.project_path) {
            projectPath = result.project_path;
            document.getElementById('projectPath').value = projectPath;
            
            // 自动加载基础配置
            await loadBaseData();
        }
        
        // 输出新方案按钮状态
        console.log("新方案按钮已初始化");
    }, 500);
    
    // 添加窗口大小变化监听器
    window.addEventListener('resize', function() {
        // 在窗口大小变化后重新应用过滤条件，确保布局正确
        if (left_search_value) {
            filterItems(left_search_value, "left");
        }
        if (right_search_value) {
            filterItems(right_search_value, "right");
        }
    });
    
    // 添加全局键盘事件监听器，捕获Ctrl/Command+S快捷键
    document.addEventListener('keydown', function(event) {
        // 检查是否按下了Ctrl键(Windows)或Command键(Mac)加S键
        if ((event.ctrlKey || event.metaKey) && event.key === 's') {
            // 阻止默认的保存行为
            event.preventDefault();
            // 调用无提示的保存函数
            save_plan_silent();
        }
    });
});

async function auto_check() {
    if(currentEditingItem){
        // 记录当前滚动位置
        const leftList = document.getElementById('leftList');
        const rightList = document.getElementById('rightList');
        const leftScrollTop = leftList.scrollTop;
        const rightScrollTop = rightList.scrollTop;
        
        // 创建一个新的任务ID
        const taskId = ++taskIdCounter;
        const modName = currentEditingItem["name"];
        
        // 在小型加载框中添加任务
        addTask(taskId, modName);
        
        try {
            // 调用后端API处理自动检查
            const wait = await pywebview.api.process_auto_check(modName);
            
            // 更新任务状态
            updateTaskStatus(taskId, "success", "更新完成");
            
            // 刷新数据但不显示全屏加载框
            await loadBaseDataSilent();
            
            // 关闭编辑模态框
            closeEditModal();
            
            // 恢复滚动位置
            setTimeout(() => {
                leftList.scrollTop = leftScrollTop;
                rightList.scrollTop = rightScrollTop;
            }, 100);
        } catch (error) {
            // 更新任务状态为错误
            updateTaskStatus(taskId, "error", error.message || "更新失败");
            console.error("自动获取过程出错:", error);
        } finally {
            // 从运行任务列表中移除
            delete runningTasks[taskId];
            // 如果没有运行中的任务，可以选择隐藏小型加载框
            if (Object.keys(runningTasks).length === 0) {
                setTimeout(() => {
                    if (Object.keys(runningTasks).length === 0) {
                        document.getElementById('miniLoadingContainer').style.display = 'none';
                    }
                }, 3000);
            }
        }
    }
}

// 添加任务到小型加载框
function addTask(taskId, modName) {
    // 显示小型加载框
    const miniLoadingContainer = document.getElementById('miniLoadingContainer');
    miniLoadingContainer.style.display = 'block';
    
    // 创建任务元素
    const taskElem = document.createElement('div');
    taskElem.id = `task-${taskId}`;
    taskElem.className = 'mini-loading-task';
    taskElem.innerHTML = `<span>${modName}: 正在更新...</span>`;
    
    // 添加到加载内容区域
    document.getElementById('miniLoadingContent').appendChild(taskElem);
    
    // 添加到运行任务列表
    runningTasks[taskId] = {
        modName: modName,
        element: taskElem
    };
}

// 更新任务状态
function updateTaskStatus(taskId, status, message) {
    const taskElem = document.getElementById(`task-${taskId}`);
    if (taskElem) {
        if (status === "success") {
            taskElem.className = 'mini-loading-task mini-loading-task-success';
            taskElem.innerHTML = `<span>${runningTasks[taskId].modName}: ${message || '更新成功'}</span>`;
        } else if (status === "error") {
            taskElem.className = 'mini-loading-task mini-loading-task-error';
            taskElem.innerHTML = `<span>${runningTasks[taskId].modName}: ${message || '更新失败'}</span>`;
        }
    }
}

// 关闭小型加载框
function closeMiniLoading() {
    document.getElementById('miniLoadingContainer').style.display = 'none';
}

// 静默加载基础数据（不显示全屏加载框）
async function loadBaseDataSilent() {
    if (!projectPath) {
        console.log('请先选择项目文件夹');
        return;
    }
    
    try {
        const result = await pywebview.api.load_base_config();
        
        if (result.status === 'success' || result.status === 'warning') {
            allItems = result.data;
            updateLists();
            
            if (result.status === 'warning') {
                console.warn(result.message);
            }
            
            // 加载完基础配置后，如果有当前方案和遮掩，自动加载它们
            if (currentPlan) {
                await loadSelectedPlanSilent();
            }
            
            if (currentMaskPlan) {
                await applyMaskWithoutAlert();
            }
        } else {
            console.error(result.message);
        }
    } catch (error) {
        console.error("加载基础数据时出错:", error);
    }
}

// 静默加载选定的方案（不显示全屏加载框）
async function loadSelectedPlanSilent() {
    if (!projectPath || !currentPlan) {
        return;
    }
    
    try {
        const result = await pywebview.api.load_plan(currentPlan);
        
        if (result.status === 'success') {
            allItems = result.data;
            updateLists();
        } else {
            console.error(result.message);
        }
    } catch (error) {
        console.error("加载方案时出错:", error);
    }
}

async function update_loading_content(id, text) {
    processing_list[id] = text;
    
    let out_str = "";
    for (const key in processing_list) {
        if (processing_list.hasOwnProperty(key)) {
            const element = processing_list[key];
            // 检查是否是重复mod消息，添加替换按钮
            if (element === 'Find duplicate mod') {
                out_str += `${key}: ${element} <button class="replace-btn" onclick="replaceDuplicateMod('${key}')">替换</button><br>`;
            } else {
                out_str += `${key}: ${element}<br>`;
            }
        }
    }
    document.getElementById('loading-content').innerHTML = out_str;
}

// 最小化加载弹窗
function minimizeLoading() {
    document.getElementById('loadingModal').style.display = 'none';
    document.getElementById('minimizedLoading').style.display = 'block';
}

// 最大化加载弹窗（恢复显示）
function maximizeLoading() {
    document.getElementById('minimizedLoading').style.display = 'none';
    document.getElementById('loadingModal').style.display = 'block';
}

// 显示加载弹窗
function showLoadingModal(showCloseButton = false) {
    document.getElementById('loadingModal').style.display = 'block';
    document.getElementById('minimizedLoading').style.display = 'none';
    document.getElementById('closeLoadingMod').style.display = showCloseButton ? 'block' : 'none';
}

// 隐藏加载弹窗
function hideLoadingModal() {
    document.getElementById('loadingModal').style.display = 'none';
    document.getElementById('minimizedLoading').style.display = 'none';
}

async function open_settings() {
    const modal = document.getElementById('settingPanel');
    modal.style.display = 'block';
    
    // 加载可用方案列表
    await loadAvailablePlans();
    
    // 设置当前遮掩方案和模式
    const maskPlanSelector = document.getElementById('maskPlanSelector');
    const maskModeSelector = document.getElementById('maskModeSelector');
    if (currentMaskPlan) {
        maskPlanSelector.value = currentMaskPlan;
    }
    if (currentMaskMode) {
        maskModeSelector.value = currentMaskMode;
    }
    
    // 加载测试指令
    const testCommand = await pywebview.api.get_test_command();
    if (testCommand) {
        document.getElementById('testCommand').value = testCommand;
    }
}

async function loadAvailablePlans() {
    if (!projectPath) {
        return;
    }
    
    const result = await pywebview.api.get_available_plans();
    if (result.status === 'success') {
        const planSelector = document.getElementById('planSelector');
        const maskPlanSelector = document.getElementById('maskPlanSelector');
        
        // 清空现有选项，保留默认选项
        planSelector.innerHTML = '<option value="">-- 选择方案 --</option>';
        maskPlanSelector.innerHTML = '<option value="">-- 无遮掩 --</option>';
        
        // 添加方案列表
        for (const plan of result.data) {
            // 为普通方案选择器添加选项
            const option = document.createElement('option');
            option.value = plan;
            option.textContent = plan;
            
            // 如果是当前方案，则选中
            if (plan === currentPlan) {
                option.selected = true;
            }
            
            planSelector.appendChild(option);
            
            // 为遮掩方案选择器添加相同的选项
            const maskOption = document.createElement('option');
            maskOption.value = plan;
            maskOption.textContent = plan;
            maskPlanSelector.appendChild(maskOption);
        }
    } else {
        alert(result.message);
    }
}

async function onPlanChange() {
    // 仅更新UI上的选择，不加载方案
    const planSelector = document.getElementById('planSelector');
    currentPlan = planSelector.value;
}

async function loadSelectedPlan() {
    if (!projectPath) {
        alert('请先选择项目文件夹');
        return;
    }
    
    const planSelector = document.getElementById('planSelector');
    const planName = planSelector.value;
    
    if (planName) {
        showLoadingModal();
        const result = await pywebview.api.load_plan(planName);
        hideLoadingModal();
        
        if (result.status === 'success') {
            currentPlan = planName;
            allItems = result.data;
            updateLists();
        } else {
            alert(result.message);
        }
    } else {
        // 清空当前方案
        const result = await pywebview.api.load_plan("");
        if (result.status === 'success') {
            currentPlan = "";
            allItems = result.data;
            updateLists();
        }
    }
}

async function add_mod() {
    if (!projectPath) {
        alert('请先选择项目文件夹');
        return;
    }
    
    showLoadingModal();
    
    const result = await pywebview.api.add_file();
    
    if (result.status === 'mask_warning') {
        // 显示在遮掩模式下添加文件的确认对话框
        if (confirm(result.message)) {
            // 用户确认，继续添加文件
            const confirmResult = await pywebview.api.confirm_add_file();
            handleAddModResult(confirmResult);
        } else {
            // 用户取消，隐藏加载框
            hideLoadingModal();
        }
    } else {
        handleAddModResult(result);
    }
}

async function manual_add_mod() {
    if (!projectPath) {
        alert('请先选择项目文件夹');
        return;
    }
    
    showLoadingModal();
    
    const result = await pywebview.api.manual_add_file();
    
    if (result.status === 'success') {
        currentData = result.data;
        updateLists();
        hideLoadingModal();
    } else {
        alert(result.message);
        hideLoadingModal();
    }
}

async function close_loading_mod() {
    hideLoadingModal();
    // 清理处理列表
    processing_list = {};
    // 通知后端清理待替换列表
    await pywebview.api.clear_pending_replacements();
}

function close_settings() {
    const modal = document.getElementById('settingPanel');
    modal.style.display = 'none';
    
    // 保存测试指令
    const testCommand = document.getElementById('testCommand').value;
    pywebview.api.save_test_command(testCommand);
}

async function save_plan() {
    if (!projectPath) {
        alert('请先选择项目文件夹');
        return;
    }
    
    // 检查是否已有加载的方案
    if (currentPlan) {
        // 直接保存到当前方案
        const result = await pywebview.api.save_current_plan();
        
        if (result.status === 'success') {
            alert(result.message || "方案已保存");
        } else {
            alert(result.message || "保存方案失败");
        }
    } else {
        // 显示输入方案名称的对话框
        const planNameModal = document.getElementById('planNameModal');
        const planNameInput = document.getElementById('planNameInput');
        
        // 清空之前的输入
        planNameInput.value = '';
        
        // 设置模态对话框标题和按钮文本，标记为保存模式
        document.querySelector('#planNameModal h2').textContent = '保存方案';
        document.querySelector('#planNameModal button').textContent = '保存';
        document.querySelector('#planNameModal button').onclick = save_plan_with_name;
        planNameInput.onkeydown = function(event) {
            if(event.key === 'Enter') save_plan_with_name();
        };
        
        // 显示模态对话框
        planNameModal.style.display = 'block';
        
        // 聚焦到输入框
        planNameInput.focus();
    }
}

async function save_plan_with_name() {
    const planNameInput = document.getElementById('planNameInput');
    const planName = planNameInput.value.trim();
    
    // 验证方案名称
    if (!planName) {
        alert('方案名称不能为空');
        return;
    }
    
    // 隐藏模态对话框
    document.getElementById('planNameModal').style.display = 'none';
    
    // 显示加载指示器
    showLoadingModal();
    
    try {
        // 调用后端API保存当前方案
        const result = await pywebview.api.save_current_plan(planName);
        
        // 隐藏加载指示器
        hideLoadingModal();
        
        if (result && result.status === 'success') {
            // 更新当前方案
            currentPlan = result.plan_name;
            allItems = result.data;
            updateLists();
            
            // 刷新方案列表并选中新方案
            await loadAvailablePlans();
            
            // 显示成功消息
            alert(result.message || "方案保存成功");
        } else {
            // 显示错误消息
            alert(result && result.message ? result.message : "保存方案失败，未知错误");
        }
    } catch (error) {
        // 隐藏加载指示器并显示错误
        hideLoadingModal();
        console.error('保存方案时出错:', error);
        alert('保存方案时出错: ' + error);
    }
}

async function export_mods() {
    if (!projectPath) {
        alert('请先选择项目文件夹');
        return;
    }
    
    if (!exportPath) {
        // 先选择导出路径
        const path = await pywebview.api.select_export_folder();
        if (!path) {
            alert('请先选择导出路径');
            return;
        }
        exportPath = path;
        document.getElementById('exportPath').value = path;
    }
    
    const result = await pywebview.api.export_selected_mods();
    
    if (result.status === 'request_plan_name') {
        // 显示输入方案名称的对话框
        document.getElementById('planNameModal').style.display = 'block';
    } else if (result.status === 'success') {
        alert(result.message);
    } else {
        alert(result.message);
    }
}

async function delete_mod() {
    if(!currentEditingItem){
        alert('请先选择一个模组');
        return;
    }
    
    if(!projectPath) {
        alert('请先选择项目文件夹');
        return;
    }
    
    const result = await pywebview.api.delete_item(currentEditingItem["name"]);
    if (result.status === 'success') {
        allItems = result.data;
        updateLists();
        alert(result.message);
    } else {
        alert(result.message);
    }
    
    document.getElementById('deleteModal').style.display = 'none'
    closeEditModal();
}

function openEditModal(item) {
    currentEditingItem = item;
    const modal = document.getElementById('editModal');
    modal.style.display = 'block';
    // 默认选中某个 tag，例如 "desc"
    document.getElementById('tagSelector').value = 'desc';
    // 如果该 tag 存在，则填充内容，否则置空
    document.getElementById('tagEditor').value = item.desc || '';
    
    // 添加删除按钮事件监听
    document.getElementById('deleteButton').onclick = function() {
        document.getElementById('deleteModal').style.display = 'block';
    };
    
    // 添加替换按钮事件监听
    document.getElementById('replaceButton').onclick = replaceMod;
}

function closeEditModal() {
    document.getElementById('editModal').style.display = 'none';
    currentEditingItem = null;
}

function onTagChange() {
    if (currentEditingItem) {
        const selectedTag = document.getElementById('tagSelector').value;
        if(selectedTag === "label" && "label" in currentEditingItem){
            document.getElementById('tagEditor').value = currentEditingItem["label"][0] || '';
        }else{
            document.getElementById('tagEditor').value = currentEditingItem[selectedTag] || '';
        }
    }
}

async function saveEdit() {
    if (currentEditingItem) {
        const selectedTag = document.getElementById('tagSelector').value;
        let newValue = document.getElementById('tagEditor').value;
        if(selectedTag === "label"){
            if ("label" in currentEditingItem){
                currentEditingItem["label"][0] = newValue;
                newValue = currentEditingItem["label"];
            }else{
                currentEditingItem["label"] = [newValue];
                newValue = currentEditingItem["label"];
            }
            
        }else{
            currentEditingItem[selectedTag] = newValue;
        }
        
        // 调用后端 API 保存更新（同时写回 JSON 文件）
        const result = await pywebview.api.update_item(currentEditingItem.name, selectedTag, newValue);
        if (result.status === 'success') {
            allItems = result.data;
            updateLists();
            closeEditModal();
        } else {
            alert(result.message);
        }
    }
}

async function selectProjectFolder() {
    const result = await pywebview.api.select_project_folder();
    if (result.status === 'success' || result.status === 'warning') {
        projectPath = result.project_path;
        document.getElementById('projectPath').value = projectPath;
        allItems = result.data;
        updateLists();
        
        if (result.status === 'warning') {
            alert(result.message);
        }
    } else {
        alert(result.message);
    }
}

async function selectExportFolder() {
    const path = await pywebview.api.select_export_folder();
    if (path) {
        exportPath = path;
        document.getElementById('exportPath').value = path;
    }
}

async function loadBaseData() {
    if (!projectPath) {
        alert('请先选择项目文件夹');
        return;
    }
    
    showLoadingModal();
    const result = await pywebview.api.load_base_config();
    hideLoadingModal();
    
    if (result.status === 'success' || result.status === 'warning') {
        allItems = result.data;
        updateLists();
        
        if (result.status === 'warning') {
            alert(result.message);
        }
        
        // 加载完基础配置后，如果有当前方案和遮掩，自动加载它们
        if (currentPlan) {
            await loadSelectedPlan();
        }
        
        if (currentMaskPlan) {
            await applyMaskWithoutAlert();
        }
    } else {
        alert(result.message);
    }
}

// 无提示地应用遮掩，供loadBaseData内部调用
async function applyMaskWithoutAlert() {
    document.getElementById('loadingModal').style.display = 'block';
    const result = await pywebview.api.set_mask_plan(currentMaskPlan, currentMaskMode);
    document.getElementById('loadingModal').style.display = 'none';
    
    if (result.status === 'success') {
        isMaskMode = !!currentMaskPlan;
        allItems = result.data;
        updateLists();
    }
}

function filterItems(searchText, side) {
    if(side === "right"){
        right_search_value = searchText;
    }else{
        left_search_value = searchText;
    }

    const listId = `${side}List`;
    const elements = document.getElementById(listId).children;
    
    Array.from(elements).forEach(element => {
      // 分别选取 banner-name 和 banner-label 元素
      const bannerNameElem = element.querySelector('.banner-filter');
      
      // 保存原始内容（只保存一次）
      if (!bannerNameElem.dataset.original) {
        bannerNameElem.dataset.original = bannerNameElem.innerHTML;
      }
      
      // 获取两个元素的文本，并转换为小写进行匹配
      const textName = bannerNameElem.textContent.toLowerCase();
      const searchLower = searchText.toLowerCase();
      
      // 如果任一元素的文本包含搜索字符串，则认为匹配
      const match = textName.includes(searchLower)
      element.style.display = match ? 'block' : 'none';
      
      if (match && searchText) {
        // 如果 banner-name 匹配，则高亮，否则恢复原始内容
        if (textName.includes(searchLower)) {
          highlightText(bannerNameElem, searchText);
        } else {
          bannerNameElem.innerHTML = bannerNameElem.dataset.original;
        }
        
      } else {
        // 搜索为空或者不匹配时，恢复原始内容
        bannerNameElem.innerHTML = bannerNameElem.dataset.original;
      }
    });
}

function highlightText(element, text) {
    // 基于原始内容进行高亮，避免重复叠加高亮标签
    const originalHTML = element.dataset.original;
    const lowerOriginal = originalHTML.toLowerCase();
    const lowerText = text.toLowerCase();
    const index = lowerOriginal.indexOf(lowerText);
    
    if (index >= 0) {
      element.innerHTML = originalHTML.substring(0, index) + 
        `<span class="highlight">${originalHTML.substr(index, text.length)}</span>` + 
        originalHTML.substring(index + text.length);
    } else {
      element.innerHTML = originalHTML;
    }
}

function updateLists() {
    const leftList = document.getElementById('leftList');
    const rightList = document.getElementById('rightList');
    
    leftList.innerHTML = '';
    rightList.innerHTML = '';
    
    let total_count = allItems.length;
    let right_count = 0;
    let left_count = 0;

    allItems.forEach(item => {
        if (item.selected) {
            const element = createBannerElement(item, "Right");
            rightList.appendChild(element);
            right_count += 1;
        } else {
            const element = createBannerElement(item, "Left");
            leftList.appendChild(element);
            left_count += 1;
        }
    });

    document.getElementById('leftTotal').innerText = `${left_count}/${total_count}`;
    document.getElementById('rightTotal').innerText = `${right_count}/${total_count}`;

    // 应用当前的过滤条件
    if (left_search_value) {
        filterItems(left_search_value, "left");
    }
    if (right_search_value) {
        filterItems(right_search_value, "right");
    }
}

function createBannerElement(item, side) {
    const div = document.createElement('div');
    div.className = 'banner';
    div.setAttribute('data-name', item.name);
    div.addEventListener('click', function() {
        toggleSelection(item.name);
    });
    
    var img_url = "";
    var label = "";
    var label_name = item.name;
    var url = item.url || "";
    var mcmod_url = item.mcmod_url || "";

    let filter_content = document.getElementById(`contentFilter${side}`).value;

    if ("img_url" in item){
        img_url = item.img_url;
    }
    if ("label" in item){
        label = item.label[0];
    }
    if("label_name" in item){
        label_name = item.label_name;
    }

    let contentHTML = `
    <div class="banner-content">
        <div class="banner-top">
            <div class="banner-info">
                <img src="${img_url}" alt="${item.name}" class="banner-img" />
                <div class="banner-text">
                    <h3 class="banner-label">[${label}]</h3>
                    <h3 class="banner-name">${label_name}</h3>
                </div>
            </div>
            <button class="edit-btn">编辑</button>
        </div>
        <p>${item.desc || ""}</p>
    `;
    
    // 添加评论（如果有）
    if ("comment" in item) {
        contentHTML += `<p class="banner-comment" style="color: #278cf1;">\n${item.comment}</p>`;
    }
    
    // 添加外部链接按钮
    contentHTML += `<div class="external-links">`;
    
    if (mcmod_url && mcmod_url.trim() !== "") {
        contentHTML += `<button class="link-btn mcmod-btn" data-url="${mcmod_url}">MCMod</button>`;
    }
    
    if (url && url.trim() !== "") {
        contentHTML += `<button class="link-btn curseforge-btn" data-url="${url}">CurseForge</button>`;
    }
    
    contentHTML += `</div>`;
    
    // 隐藏过滤内容
    contentHTML += `<p class="banner-filter" style="display: none;">${item[filter_content] || ""}</p>`;
    contentHTML += `</div>`;
    
    div.innerHTML = contentHTML;

    // 为编辑按钮添加事件监听
    const editBtn = div.querySelector('.edit-btn');
    editBtn.addEventListener('click', (e) => {
        e.stopPropagation(); // 阻止点击 banner 触发其他事件
        openEditModal(item);
    });
    
    // 为链接按钮添加点击事件
    const linkButtons = div.querySelectorAll('.link-btn');
    linkButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation(); // 阻止点击按钮触发选择模组
            pywebview.api.open_url(btn.dataset.url);
        });
    });

    return div;
}

async function toggleSelection(itemName) {
    const result = await pywebview.api.toggle_mod_selection(itemName);
    if (result.status === 'success') {
        allItems = result.data;
        updateLists();
        filterItems(right_search_value, "right");
        filterItems(left_search_value, "left");
    }
}

async function test_game() {
    const result = await pywebview.api.run_test_command();
    if (result.status === 'error') {
        alert(result.message);
    }
}

async function replaceMod() {
    if(!currentEditingItem){
        alert('请先选择一个模组');
        return;
    }
    
    if(!projectPath) {
        alert('请先选择项目文件夹');
        return;
    }
    
    if(confirm(`确定要替换模组 ${currentEditingItem.name} 吗？`)) {
        const result = await pywebview.api.replace_mod(currentEditingItem.name);
        if (result.status === 'success') {
            allItems = result.data;
            updateLists();
            alert(result.message);
            closeEditModal();
        } else {
            alert(result.message);
        }
    }
}

async function createNewPlan() {
    if (!projectPath) {
        alert('请先选择项目文件夹');
        return;
    }
    
    // 使用模态对话框而不是简单的prompt
    const planNameModal = document.getElementById('planNameModal');
    const planNameInput = document.getElementById('planNameInput');
    
    // 清空之前的输入
    planNameInput.value = '';
    
    // 设置模态对话框标题和按钮文本，标记为创建模式
    document.querySelector('#planNameModal h2').textContent = '创建新方案';
    document.querySelector('#planNameModal button').textContent = '创建方案';
    document.querySelector('#planNameModal button').onclick = create_new_plan_with_name;
    planNameInput.onkeydown = function(event) {
        if(event.key === 'Enter') create_new_plan_with_name();
    };
    
    // 显示模态对话框
    planNameModal.style.display = 'block';
    
    // 聚焦到输入框
    planNameInput.focus();
}

async function create_new_plan_with_name() {
    const planNameInput = document.getElementById('planNameInput');
    const planName = planNameInput.value.trim();
    
    // 验证方案名称
    if (!planName) {
        alert('方案名称不能为空');
        return;
    }
    
    // 隐藏模态对话框
    document.getElementById('planNameModal').style.display = 'none';
    
    // 显示加载指示器
    showLoadingModal();
    
    try {
        console.log("正在创建新方案:", planName);
        // 调用后端API创建新方案
        const result = await pywebview.api.create_new_plan(planName);
        
        // 隐藏加载指示器
        hideLoadingModal();
        
        console.log("创建方案返回结果:", result);
        
        if (result && result.status === 'success') {
            // 更新当前方案和数据
            currentPlan = planName;
            allItems = result.data;
            updateLists();
            
            // 刷新方案列表并选中新方案
            await loadAvailablePlans();
            
            // 在方案选择器中选中新方案
            const planSelector = document.getElementById('planSelector');
            planSelector.value = planName;
            
            // 显示成功消息
            alert(result.message || "新方案创建成功");
        } else {
            // 显示错误消息
            alert(result && result.message ? result.message : "创建方案失败，未知错误");
        }
    } catch (error) {
        // 隐藏加载指示器并显示错误
        hideLoadingModal();
        console.error('创建方案时出错:', error);
        alert('创建方案时出错: ' + error);
    }
}

async function applyMask() {
    if (!projectPath) {
        alert('请先选择项目文件夹');
        return;
    }
    
    const maskPlanSelector = document.getElementById('maskPlanSelector');
    const maskModeSelector = document.getElementById('maskModeSelector');
    
    const maskPlan = maskPlanSelector.value;
    const maskMode = maskModeSelector.value;
    
    showLoadingModal();
    const result = await pywebview.api.set_mask_plan(maskPlan, maskMode);
    hideLoadingModal();
    
    if (result.status === 'success') {
        currentMaskPlan = maskPlan;
        currentMaskMode = maskMode;
        isMaskMode = !!maskPlan;
        allItems = result.data;
        updateLists();
        alert(result.message);
    } else {
        alert(result.message);
    }
}

// 辅助函数处理添加mod的结果
function handleAddModResult(result) {
    if (result.status === 'success') {
        currentData = result.data;
        updateLists();
        // 显示关闭按钮
        document.getElementById('closeLoadingMod').style.display = 'block';
    } else if (result.status === 'error') {
        alert(result.message);
        hideLoadingModal();
    }
}

async function clearAndReload() {
    // 清空当前方案和遮掩设置
    currentPlan = "";
    currentMaskPlan = "";
    currentMaskMode = "include";
    isMaskMode = false;
    
    // 更新选择器UI
    const planSelector = document.getElementById('planSelector');
    const maskPlanSelector = document.getElementById('maskPlanSelector');
    const maskModeSelector = document.getElementById('maskModeSelector');
    
    planSelector.value = "";
    maskPlanSelector.value = "";
    maskModeSelector.value = "include";
    
    // 加载基础配置（不应用任何方案或遮掩）
    showLoadingModal();
    
    // 先清空当前方案
    await pywebview.api.load_plan("");
    
    // 再清空遮掩
    await pywebview.api.set_mask_plan("", "include");
    
    // 重新加载基础配置
    const result = await pywebview.api.load_base_config();
    hideLoadingModal();
    
    if (result.status === 'success' || result.status === 'warning') {
        allItems = result.data;
        updateLists();
        
        if (result.status === 'warning') {
            alert(result.message);
        }
        
        alert("已清空当前方案和遮掩设置并重新加载");
    } else {
        alert(result.message);
    }
}

// 添加替换重复mod的函数
async function replaceDuplicateMod(modName) {
    try {
        // 禁用该按钮，防止重复点击
        const buttons = document.querySelectorAll('.replace-btn');
        buttons.forEach(btn => {
            if (btn.parentElement.textContent.includes(modName)) {
                btn.disabled = true;
                btn.textContent = "替换中...";
            }
        });
        
        // 调用API替换重复mod
        const result = await pywebview.api.replace_duplicate_mod(modName);
        
        if (result.status === 'success') {
            // 更新处理状态消息
            processing_list[modName] = "替换成功，旧版本已被新版本替换";
            update_loading_content(modName, processing_list[modName]);
        } else {
            // 替换失败，恢复按钮
            processing_list[modName] = `替换失败: ${result.message}`;
            update_loading_content(modName, processing_list[modName]);
        }
    } catch (error) {
        console.error('替换mod时出错:', error);
        processing_list[modName] = `替换出错: ${error}`;
        update_loading_content(modName, processing_list[modName]);
    }
}

// 无提示保存函数 - 通过快捷键调用时使用
async function save_plan_silent() {
    if (!projectPath) {
        console.log('请先选择项目文件夹');
        return;
    }
    
    // 检查是否已有加载的方案
    if (currentPlan) {
        // 直接保存到当前方案
        const result = await pywebview.api.save_current_plan();
        
        if (result.status === 'success') {
            console.log(result.message || "方案已保存");
            // 可以添加一个临时提示，显示几秒后自动消失
            const saveIndicator = document.createElement('div');
            saveIndicator.textContent = '已保存';
            saveIndicator.style.position = 'fixed';
            saveIndicator.style.bottom = '20px';
            saveIndicator.style.right = '20px';
            saveIndicator.style.backgroundColor = 'rgba(0, 128, 0, 0.7)';
            saveIndicator.style.color = 'white';
            saveIndicator.style.padding = '10px 20px';
            saveIndicator.style.borderRadius = '5px';
            saveIndicator.style.zIndex = '9999';
            document.body.appendChild(saveIndicator);
            
            // 2秒后移除提示
            setTimeout(() => {
                document.body.removeChild(saveIndicator);
            }, 2000);
        } else {
            console.error(result.message || "保存方案失败");
        }
    } else {
        // 如果没有当前方案，打开保存对话框
        document.getElementById('planNameModal').style.display = 'block';
        document.querySelector('#planNameModal h2').textContent = '保存方案';
        document.querySelector('#planNameModal button').textContent = '保存';
        document.querySelector('#planNameModal button').onclick = save_plan_with_name;
        document.getElementById('planNameInput').focus();
    }
}