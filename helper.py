import requests
from bs4 import BeautifulSoup
import urllib.parse
import webbrowser
from googlesearch import search
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
import time
import random
import threading
from openai import OpenAI
import re
import urllib3
import easyocr
import os
import tempfile
from io import BytesIO
from PIL import Image
from selenium.webdriver.common.by import By
import ssl
import certifi
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import dotenv
# 禁用SSL证书验证警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 解决SSL证书验证失败问题
ssl._create_default_https_context = ssl._create_unverified_context

# 设置requests使用certifi提供的证书
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
os.environ['SSL_CERT_FILE'] = certifi.where()

lock = threading.Lock()
proxy_url = 'http://127.0.0.1:10080/'
proxy_url_url = 'http://127.0.0.1:10080'

dotenv.load_dotenv()

API_KEY = os.getenv("API_KEY")
MODEL = os.getenv("MODEL")
BASE_URL = os.getenv("BASE_URL")

def check_proxy_available(proxy_url_):
    """
    检查代理是否可用
    """
    try:
        proxies = {
            'http': proxy_url_,
            'https': proxy_url_
        }
        response = requests.get('https://www.bing.com', proxies=proxies, timeout=5, verify=False)
        return response.status_code == 200
    except Exception:
        return False
            
class OpenAIClient:
    def __init__(self):
        self.client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
        self.model = MODEL

    def get_mod_description(self, text):
        """调用OpenAI API获取MOD描述"""
        prompt = """
            你是一个Minecraft 1.20 Forge Mod的功能说明助手
            用户会给你一段这个Mod的官方介绍，你需要根据官方介绍用中文总结一下这个Mod的功能，内容和玩法(只输出文字，不要带任何格式符号)
            注意，你只需要关注和模组功能性相关的内容和介绍中有关稳定性(部分可能会说有bug风险)的部分，不需要关注其他任何内容。
            介绍尽量在不流失重要信息的情况下保持简介。
            """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text}
                ],
                # max_tokens=50
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"API调用失败：{str(e)}")
            return ""


ai = OpenAIClient()

def get_label_from_url(url):
    try:
        options = uc.ChromeOptions()
        # options.headless = True
        # options.add_argument("--window-position=-32000,0")
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--ignore-ssl-errors')

        # 设置页面加载策略为急切模式，不等待完全加载
        options.page_load_strategy = 'eager'
        if check_proxy_available(proxy_url):
            options.add_argument(f'--proxy-server={proxy_url_url}')
        driver = uc.Chrome(options=options, version_main=132, ssl_verify=False)
        # driver.minimize_window()
        
        # 设置脚本超时，防止页面长时间加载
        # driver.set_script_timeout(10)
        # driver.set_page_load_timeout(15)
        
        # 使用JavaScript停止页面在必要元素加载完成后继续加载
        driver.get(url)
        driver.execute_script("window.stop();")
        
        # ------------------ 任务1 ------------------
        mod_name = ""
        label = []
        final_text = ""
        try:
            # 使用显式等待等待元素出现，最多等待10秒
            wait = WebDriverWait(driver, 10)
            class_title_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".class-title")))
            h3_elements = class_title_elem.find_elements(By.TAG_NAME, "h3")
            h4_elements = class_title_elem.find_elements(By.TAG_NAME, "h4")
            task1_texts = [el.text.strip() for el in h3_elements + h4_elements if el.text.strip()]
            for text in task1_texts:
                mod_name += (text + " ")
        
        except TimeoutException:
            print("任务1 超时：未能在指定时间内找到元素")
            driver.quit()
            return None
        except Exception as e:
            print("任务1 出现异常：", e)
            driver.quit()
            return None
        
        try:
            # 使用显式等待等待元素出现
            common_category_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".common-class-category")))
            png_data = common_category_elem.screenshot_as_png
            image = Image.open(BytesIO(png_data))
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                temp_path = tmp.name
                image.save(temp_path)
            reader = easyocr.Reader(['ch_sim'], gpu=True)
            ocr_text = reader.readtext(temp_path)
            ocr_text = [item[1] for item in ocr_text]
            os.remove(temp_path)
            label = ocr_text
        except TimeoutException:
            print("任务2 超时：未能在指定时间内找到元素")
            driver.quit()
            return None
        except Exception as e:
            print("任务2 出现异常：", e)
            driver.quit()
            return None
        
        # ------------------ 任务3 ------------------
        try:
            # 使用显式等待等待元素出现
            elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".class-info")))
            if elements:
                li_elements = elements[0].find_elements(By.CSS_SELECTOR, ".col-lg-4")
                task3_texts = [el.text.strip() for el in li_elements if el.text.strip()]
                final_text = ""
                for text in task3_texts:
                    if("运行环境: " in text):
                        final_text = text.split("运行环境: ", 1)[1]
                        break
        except TimeoutException:
            print("任务3 超时：未能在指定时间内找到元素")
            # 即使任务3失败，如果前两个任务成功，我们仍然可以返回有用的信息
            pass
        except Exception as e:
            print("任务3 出现异常：", e)
            # 即使任务3失败，如果前两个任务成功，我们仍然可以返回有用的信息
            pass
        
        driver.quit()
        return [mod_name, label, final_text]
    except Exception as e:
        print("出现异常：", e)
        if 'driver' in locals() and driver:
            driver.quit()
        return None


def get_text_from_url(url):
    options = uc.ChromeOptions()
    # options.headless = True  # 可根据需要选择无头模式
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors')

    if check_proxy_available(proxy_url):
        options.add_argument(f'--proxy-server={proxy_url_url}')
    # 设置页面加载策略为急切模式，不等待完全加载
    options.page_load_strategy = 'eager'
    driver = None
    try:
        driver = uc.Chrome(options=options, version_main=132, ssl_verify=False)
        # driver.minimize_window()
        
        # 设置脚本超时，防止页面长时间加载
        driver.set_script_timeout(10)
        driver.set_page_load_timeout(15)
        
        driver.get(url)
        # 使用JavaScript停止页面在必要元素加载完成后继续加载
        driver.execute_script("window.stop();")
        
        try:
            # 使用短暂等待确保基本DOM已加载
            time.sleep(random.uniform(0.5, 1))
            
            # 使用显式等待等待元素出现
            wait = WebDriverWait(driver, 10)
            
            # 获取页面文本
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(separator="\n")
            
            # 分割逻辑
            if "CurseForge - a world" in text:
                text = text.split("CurseForge - a world", 1)[0]
            if "Issues" in text:
                text = text.split("Issues", 1)[1]

            text = text.strip()

            # 等待并获取图片元素
            try:
                class_title_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".project-header")))
                h3_elements = class_title_elem.find_elements(By.TAG_NAME, "img")
                if h3_elements and len(h3_elements) > 0:
                    img = h3_elements[0].get_attribute("src")
                    return [text, img]
                return [text, ""]
            except TimeoutException:
                print("图片元素加载超时，仅返回文本")
                return [text, ""]
        except TimeoutException:
            print("页面元素加载超时")
            return None
        except Exception as e:
            print("任务4 出现异常：", e)
            return None
    except Exception as e:
        print("出现异常：", e)
        return None
    finally:
        if driver:
            driver.quit()


def google_search(query, domain_filter="www.curseforge.com", region="hk", num_results=10):
    """
    在 Google 中搜索 query，并返回第一个包含 domain_filter 的搜索结果链接。
    """
    # 编码搜索词，构造搜索 URL
    try:

        if check_proxy_available(proxy_url):
            result = search(query, region=region, num_results=num_results, proxy=proxy_url, ssl_verify=False)
        else:
            # 代理不可用，不使用代理
            result = search(query, region=region, num_results=num_results, ssl_verify=False)


        if domain_filter is None:
            return result
        

        for i in result:
            if domain_filter in i:
                if "/files" in i:
                    rtn = i.split("/files", 1)[0]
                else:
                    rtn = i

                return rtn
            
    except Exception as e:
        return None
    
    return None


def process_get_url(i):
    m = re.match(r'^(\[[^]]*\]\s*)(.*)', i['name'])
    if m:
        name = m.group(2)
    else:
        name = i['name']

    if ("url" in i.keys() and i["url"]):
        return
    
    result_links = google_search(name, domain_filter=None, num_results=15, region="us")
    result_link = None
    for link in result_links:
        if "www.curseforge.com/minecraft/mc-mods/" in link:
            if "/files" in link:
                result_link = link.split("/files", 1)[0]
            else:
                result_link = link
            break
    # www.curseforge.com/minecraft/mc-mods/
    if result_link:
        i["url"] = result_link
        return True
    
    return False


def process_get_url_mcmod(i):
    if not("url" in i.keys() and i["url"]) or ("mcmod_url" in i.keys() and i["mcmod_url"]):
        return

    name = i["url"].split("/")[-1] + " mcmod"
    pattern = r"^https://www\.mcmod\.cn/class/\d+\.html$"

    result_links = google_search(name, domain_filter=None, num_results=15, region="hk")
    result_link = None
    for link in result_links:
        if re.match(pattern, link):
            result_link= link
            break


    if result_link:
        i["mcmod_url"] = result_link
        return True

    return False


def get_url(json_data, max_workers=8, mcmod=False):
    # 读取 JSON 文件
    with open(json_data, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    total = len(data)
    processed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        if mcmod:
            futures = {executor.submit(process_get_url_mcmod, i): i for i in data}
        else:
            futures = {executor.submit(process_get_url, i): i for i in data}
        for future in as_completed(futures):
            future.result()
            processed += 1
            # 用 \r 回退到行首覆盖之前的进度信息，flush 确保实时输出
            print(f"Progress: {processed}/{total}", end="\r", flush=True)

    # 保存结果
    with open(json_data, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Done.")

def process_get_text(i):
    if "url" not in i.keys() or not i["url"]:
        return
        
    url = i["url"]
    result = get_text_from_url(url)
    if result:
        i["web_text"] = result[0]
        i["img_url"] = result[1]
        return True
    
    return False

def get_text(json_data, max_workers=1):
    # 读取 JSON 文件
    with open(json_data, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    total = len(data)
    processed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_get_text, i): i for i in data}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"任务出错：{e}")
            with lock:
                processed += 1
                print(f"Progress: {processed}/{total}", end="\r", flush=True)
    # 保存结果
    with open(json_data, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Done.")


def process_get_summary(i):
    if "web_text" not in i.keys() or not i["web_text"] or i["web_text"] == "":
        return False
    
    info = i["web_text"]
    text = ai.get_mod_description(info)
    if text:
        i["desc"] = text
        return True
    return False

def get_summary(json_data, max_workers=10):
    # 读取 JSON 文件
    with open(json_data, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    total = len(data)
    processed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_get_summary, i): i for i in data}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"任务出错：{e}")
            with lock:
                processed += 1
                print(f"Progress: {processed}/{total}", end="\r", flush=True)
    # 保存结果
    with open(json_data, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Done.")

def process_get_label(i):
    if "label_name" in i.keys() and "label" in i.keys() and "install" in i.keys() and i["label_name"] and i["label"] and i["install"] and i["label_name"] != "" and i["label"] != "" and i["install"] != "":
        return
    
    if "mcmod_url" not in i.keys() or not i["mcmod_url"]:
        return
        
    url = i["mcmod_url"]
    labels = get_label_from_url(url)
    if labels:
        i["label_name"] = labels[0]
        i["label"] = labels[1]
        i["install"] = labels[2]
        return True
    
    return False

def get_label(json_data, max_workers=1):
    # 读取 JSON 文件
    with open(json_data, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    total = len(data)
    processed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_get_label, i): i for i in data}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"任务出错：{e}")
            with lock:
                processed += 1
                print(f"Progress: {processed}/{total}", end="\r", flush=True)
    # 保存结果
    with open(json_data, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Done.")


#__next > div > main > div.ads-layout > div.ads-layout-content > div > div
def fix_mcmod_url(json_data):
    with open(json_data, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    for i in data:
        if "mcmod_url" not in i.keys() and "url" in i.keys():
            # name = i["name"].split("-", 1)[0] + " mcmod"
            name = i["url"].split("/")[-1] + " mcmod"
            result = google_search(name, domain_filter="www.mcmod.cn/class/", num_results=30)
            if result:
                i["mcmod_url"] = result
            else:
                i["mcmod_url"] = None

    with open(json_data, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Done.")

def get_comment_from_url(url, detail=False):
    """从MCMod网站获取评论内容
    
    Args:
        url: MCMod的URL
        detail: 是否开启详细模式，开启后会翻页获取更多评论
    """
    try:
        options = uc.ChromeOptions()
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--ignore-ssl-errors')
        if check_proxy_available(proxy_url):
            options.add_argument(f'--proxy-server={proxy_url_url}')
        # 使用normal加载策略以确保页面加载更完整
        options.page_load_strategy = 'normal'
        driver = uc.Chrome(options=options, version_main=132, ssl_verify=False)
        
        # 设置隐式等待时间，增加页面稳定性
        # driver.implicitly_wait(10)
        
        # 打开网页，并等待页面基本加载
        print(f"正在打开网页: {url}")
        driver.get(url)
        
        # 等待页面加载，先等待一个必定存在的元素
        try:
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            print("页面基本元素已加载")
        except:
            print("等待页面基本元素超时，继续执行")
        
        all_comments = []  # 存储所有评论
        current_page = 1
        continue_next_page = True
        date_cutoff = "2024-05-01"  # 日期截止点
        
        while continue_next_page:
            try:
                print(f"正在获取第 {current_page} 页评论...")
                # 等待页面稳定一下
                time.sleep(3)
                
                # 模拟滚动到页面底部，以触发评论区的懒加载
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.7);")
                time.sleep(1)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                # 再滚动几次，确保所有内容都被加载
                for _ in range(3):
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1)
                
                # 滚动到评论区位置
                try:
                    # 先尝试定位评论区的父容器
                    comment_container = None
                    possible_selectors = [".comment-list", ".class-comment", "#comment-box"]
                    
                    for selector in possible_selectors:
                        try:
                            comment_container = driver.find_element(By.CSS_SELECTOR, selector)
                            if comment_container:
                                print(f"找到评论区容器: {selector}")
                                break
                        except:
                            continue
                    
                    if comment_container:
                        # 滚动到评论区的位置
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", comment_container)
                        
                except Exception as e:
                    print(f"定位评论区失败: {e}")
                    # 如果找不到具体的评论区元素，继续使用滚动到底部的方式
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    
                
                # 使用显式等待等待评论区元素出现
                wait = WebDriverWait(driver, 10)
                # 初始化 comment_elements
                comment_elements = []
                
                try:
                    wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".comment-limit")))
                    comment_elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".comment-floor")))
                    print(f"找到 {len(comment_elements)} 页评论")
                except Exception as e:
                    print(f"获取评论元素失败: {e}")
                
                # 检查是否找到评论
                if len(comment_elements) == 0:
                    print("没有找到评论元素，跳过当前页")
                    break
                
                page_comments = []
                # 获取当前页的评论
                for comment_elem in comment_elements:
                    comment_text = comment_elem.text.strip()
                    if comment_text:
                        page_comments.append(comment_text)
                        # 检查是否有早于截止日期的评论
                        if detail and re.search(r"\d{4}-\d{2}-\d{2}", comment_text):
                            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", comment_text)
                            if date_match and date_match.group(1) < date_cutoff:
                                print(f"发现早于 {date_cutoff} 的评论，停止翻页")
                                continue_next_page = False
                                break
                
                # 将当前页评论添加到总评论列表
                all_comments.extend(page_comments)
                
                # 如果不是详细模式或已达到条件限制，停止翻页
                if not detail or not continue_next_page:
                    break
                
                # 尝试查找并点击"后页"按钮
                try:
                    # 先滚动到分页区域
                    pagination = driver.find_elements(By.CSS_SELECTOR, ".pagination")
                    if pagination:
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", pagination[0])
                        time.sleep(1)
                    
                    # 查找所有分页链接
                    next_page_links = driver.find_elements(By.CSS_SELECTOR, ".page-link")
                    next_page_button = None
                    
                    # 查找"后页"按钮
                    for link in next_page_links:
                        if link.text.strip() == "后页":
                            next_page_button = link
                            print("找到后页按钮")
                            break
                    
                    if next_page_button:
                        # 确保按钮可见并可点击
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_page_button)
                        time.sleep(1)
                        
                        # 尝试使用JavaScript点击，避免被其他元素拦截
                        try:
                            print("尝试使用JavaScript点击后页按钮")
                            driver.execute_script("arguments[0].click();", next_page_button)
                        except Exception as js_e:
                            print(f"JavaScript点击失败: {js_e}")
                            try:
                                # 如果JavaScript点击失败，尝试常规点击
                                print("尝试常规点击后页按钮")
                                next_page_button.click()
                            except Exception as click_e:
                                print(f"常规点击也失败: {click_e}")
                                # 实在不行，尝试直接修改URL跳转到下一页
                                try:
                                    next_page = current_page + 1
                                    current_url = driver.current_url
                                    if "?page=" in current_url:
                                        next_url = re.sub(r'\?page=\d+', f'?page={next_page}', current_url)
                                    else:
                                        next_url = f"{current_url}?page={next_page}"
                                    print(f"尝试直接访问下一页URL: {next_url}")
                                    driver.get(next_url)
                                except Exception as url_e:
                                    print(f"URL跳转失败: {url_e}")
                                    continue_next_page = False
                                    break
                                    
                        # 等待页面加载
                        time.sleep(3)
                        current_page += 1
                    else:
                        print("没有找到后页按钮，翻页结束")
                        continue_next_page = False
                except Exception as e:
                    print(f"翻页过程中出现异常: {e}")
                    continue_next_page = False
            
            except TimeoutException:
                print("评论元素加载超时")
                break
            except Exception as e:
                print(f"获取评论时出现异常: {e}")
                break
        
        # 如果是详细模式，打印统计信息
        if detail:
            print(f"共获取了 {len(all_comments)} 条评论，来自 {current_page} 页")
        
        # 将所有评论合并为一个字符串
        comments_text = "\n".join(all_comments)
        driver.quit()
        return comments_text
    
    except Exception as e:
        print(f"评论获取过程中出现异常: {e}")
        if 'driver' in locals() and driver:
            driver.quit()
        return None

def process_get_comment(i, detail=False):
    """处理获取评论并分析风险的函数
    
    Args:
        i: 要处理的mod条目
        detail: 是否开启详细模式获取多页评论
    """
    # 如果已经有mcmod评论，跳过
    if "mcmod_comment_text" in i and i["mcmod_comment_text"] and i["mcmod_comment_text"] != "":
        # 但如果没有分析结果，仍需分析
        if "comment" not in i or "【Mod风险分析】" not in i.get("comment", ""):
            if process_analyze_comment(i):
                return True
        return True
    
    # 检查是否有mcmod_url
    if "mcmod_url" not in i or not i["mcmod_url"]:
        return False
    
    url = i["mcmod_url"]
    comments = get_comment_from_url(url, detail=detail)
    if comments:
        i["mcmod_comment_text"] = comments
        # 获取评论后进行分析
        return process_analyze_comment(i)
    
    return False

def process_analyze_comment(i):
    """分析评论内容，评估mod风险"""
    if "mcmod_comment_text" not in i or not i["mcmod_comment_text"]:
        return False
    
    # 准备向AI提问的内容
    mod_name = i.get("label_name", i.get("name", "未知模组"))
    comment_text = i["mcmod_comment_text"]
    
    # 调用AI分析评论
    analysis = ai_analyze_mod_risk(mod_name, comment_text)
    if analysis:
        # 添加到评论字段
        if "comment" not in i or not i["comment"]:
            i["comment"] = f"【Mod风险分析】\n{analysis}"
        else:
            # 确保不重复添加风险分析
            if "【Mod风险分析】" not in i["comment"]:
                i["comment"] += f"\n\n【Mod风险分析】\n{analysis}"
        return True
    
    return False

def ai_analyze_mod_risk(mod_name, comment_text):
    """使用AI分析mod风险"""
    prompt = f"""
    你是一个Minecraft 1.20.1 mod bug排查助手。
    请根据以下评论内容，分析使用"{mod_name}"这个mod可能存在的问题，并指出使用时需要特别注意的事项，特别是对服务器, 卡顿, 生成频率相关的问题或担忧。
    
    请以简短的bullet points形式列出：
    需要注意1: 具体需要注意的内容 + 可能的解决方法或者需要调整的地方
    需要注意2: 具体需要注意的内容 + 可能的解决方法或者需要调整的地方
    ...

    如果完全没有任何风险就只输出 无风险 三个字

    请确保回答简洁清晰，每点不超过一两句话。如果评论内容中没有明确提到风险或问题，请说明"根据评论内容，未发现明显风险"。
    
    评论内容:
    {comment_text}
    """
    
    try:
        response = ai.client.chat.completions.create(
            model=ai.model,
            messages=[
                {"role": "system", "content": "你是一个Minecraft mod风险分析专家，擅长从用户评论中识别潜在问题。"},
                {"role": "user", "content": prompt}
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"AI风险分析调用失败：{str(e)}")
        return ""

def get_comment(json_data, max_workers=2):
    """批量获取评论"""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for i in json_data:
            futures.append(executor.submit(process_get_comment, i))
        
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"处理评论时出错: {e}")
    
    # 更新JSON文件
    return json_data

if __name__ == "__main__":
    json_data = r"total_ogn.json"


    # fix_mcmod_url(json_data)
    # get_label(json_data, max_workers=1)

    # with open(json_data, "r", encoding="utf-8") as f:
    #     data = json.load(f)

    # count = 0
    # for i in data:
    #     if "web_text" not in i.keys() or i["web_text"] == "No text found." or i["web_text"] == "":
    #         print(i["name"])
    #         count += 1

    # print(count)
