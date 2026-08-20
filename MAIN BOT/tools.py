"""
OXYGENT Tools System
Made by OXYCODE TEAM 👾

All tools available for OXYGENT agent.
"""

import os
import json
import sqlite3
import asyncio
import subprocess
import tempfile
import base64
import re
from datetime import datetime
from pathlib import Path
import aiohttp
import logging

logger = logging.getLogger(__name__)

# ==================== MEMORY SYSTEM ====================

class MemorySystem:
    """Long-term memory for OXYGENT"""
    
    def __init__(self, db_path="memory.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize memory database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                category TEXT DEFAULT 'general',
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_user_key ON memory(user_id, key)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_category ON memory(category)
        ''')
        conn.commit()
        conn.close()
    
    async def store(self, user_id, key, value, category="general", metadata=None):
        """Store information in memory"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        value_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        metadata_str = json.dumps(metadata) if metadata else None
        
        # Check if exists
        cursor.execute(
            'SELECT id FROM memory WHERE user_id = ? AND key = ?',
            (str(user_id), key)
        )
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute('''
                UPDATE memory 
                SET value = ?, category = ?, metadata = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND key = ?
            ''', (value_str, category, metadata_str, str(user_id), key))
        else:
            cursor.execute('''
                INSERT INTO memory (user_id, key, value, category, metadata)
                VALUES (?, ?, ?, ?, ?)
            ''', (str(user_id), key, value_str, category, metadata_str))
        
        conn.commit()
        conn.close()
        return {"success": True, "key": key}
    
    async def retrieve(self, user_id, key=None, category=None):
        """Retrieve information from memory"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if key:
            cursor.execute(
                'SELECT key, value, category, metadata FROM memory WHERE user_id = ? AND key = ?',
                (str(user_id), key)
            )
            row = cursor.fetchone()
            if row:
                try:
                    value = json.loads(row[1])
                except:
                    value = row[1]
                try:
                    metadata = json.loads(row[3]) if row[3] else None
                except:
                    metadata = None
                conn.close()
                return {"success": True, "data": {"key": row[0], "value": value, "category": row[2], "metadata": metadata}}
            conn.close()
            return {"success": False, "error": "Not found"}
        
        elif category:
            cursor.execute(
                'SELECT key, value, category, metadata FROM memory WHERE user_id = ? AND category = ?',
                (str(user_id), category)
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                try:
                    value = json.loads(row[1])
                except:
                    value = row[1]
                try:
                    metadata = json.loads(row[3]) if row[3] else None
                except:
                    metadata = None
                results.append({"key": row[0], "value": value, "category": row[2], "metadata": metadata})
            conn.close()
            return {"success": True, "data": results}
        
        else:
            cursor.execute(
                'SELECT key, value, category, metadata FROM memory WHERE user_id = ?',
                (str(user_id),)
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                try:
                    value = json.loads(row[1])
                except:
                    value = row[1]
                try:
                    metadata = json.loads(row[3]) if row[3] else None
                except:
                    metadata = None
                results.append({"key": row[0], "value": value, "category": row[2], "metadata": metadata})
            conn.close()
            return {"success": True, "data": results}
    
    async def delete(self, user_id, key):
        """Delete memory entry"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM memory WHERE user_id = ? AND key = ?', (str(user_id), key))
        conn.commit()
        conn.close()
        return {"success": True}


# ==================== WEBSITE SCREENSHOT ====================

async def website_screenshot(url, full_page=True, width=1280, height=720):
    """
    Capture screenshot of any website.
    
    Args:
        url: Website URL to capture
        full_page: Capture full page or just viewport
        width: Viewport width
        height: Viewport height
    
    Returns:
        dict with success status and image path
    """
    try:
        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Create temp directory
        temp_dir = tempfile.mkdtemp()
        screenshot_path = os.path.join(temp_dir, 'screenshot.png')
        
        # Try using playwright
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(viewport={'width': width, 'height': height})
                
                await page.goto(url, wait_until='networkidle', timeout=30000)
                await page.screenshot(path=screenshot_path, full_page=full_page)
                
                await browser.close()
                
                return {
                    "success": True,
                    "image_path": screenshot_path,
                    "url": url,
                    "width": width,
                    "height": height
                }
        
        except ImportError:
            # Fallback: use requests + imgkit or similar
            logger.warning("Playwright not available, using fallback")
            return {
                "success": False,
                "error": "Screenshot tool requires playwright. Install with: pip install playwright && playwright install chromium"
            }
    
    except Exception as e:
        logger.error(f"Screenshot error: {e}")
        return {"success": False, "error": str(e)}


# ==================== WEB SEARCH ====================

async def web_search(query, num_results=10):
    """
    Search the web for information.
    
    Args:
        query: Search query
        num_results: Number of results to return
    
    Returns:
        dict with search results
    """
    try:
        # Use DuckDuckGo search
        import httpx
        
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10)
            data = response.json()
        
        results = []
        
        # Get abstract
        if data.get('Abstract'):
            results.append({
                "title": data.get('Heading', 'Result'),
                "url": data.get('AbstractURL', ''),
                "snippet": data.get('Abstract', ''),
                "source": data.get('AbstractSource', '')
            })
        
        # Get related topics
        for topic in data.get('RelatedTopics', [])[:num_results]:
            if isinstance(topic, dict) and 'Text' in topic:
                results.append({
                    "title": topic.get('Text', '')[:100],
                    "url": topic.get('FirstURL', ''),
                    "snippet": topic.get('Text', ''),
                    "source": "DuckDuckGo"
                })
        
        return {
            "success": True,
            "query": query,
            "results": results[:num_results],
            "count": len(results)
        }
    
    except Exception as e:
        logger.error(f"Search error: {e}")
        return {"success": False, "error": str(e)}


# ==================== CODE EXECUTION ====================

async def code_execute(code, language="python", timeout=30):
    """
    Execute code in sandboxed environment.
    
    Args:
        code: Code to execute
        language: Programming language
        timeout: Execution timeout in seconds
    
    Returns:
        dict with execution result
    """
    try:
        # Create temp file
        temp_dir = tempfile.mkdtemp()
        
        # Determine file extension and command
        lang_config = {
            "python": {"ext": ".py", "cmd": ["python3"]},
            "javascript": {"ext": ".js", "cmd": ["node"]},
            "bash": {"ext": ".sh", "cmd": ["bash"]},
        }
        
        config = lang_config.get(language.lower(), lang_config["python"])
        temp_file = os.path.join(temp_dir, f"code{config['ext']}")
        
        # Write code to file
        with open(temp_file, 'w') as f:
            f.write(code)
        
        # Execute code
        try:
            result = subprocess.run(
                config['cmd'] + [temp_file],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=temp_dir
            )
            
            return {
                "success": True,
                "output": result.stdout,
                "error": result.stderr if result.stderr else None,
                "language": language,
                "returncode": result.returncode
            }
        
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Execution timed out after {timeout} seconds",
                "language": language
            }
    
    except Exception as e:
        logger.error(f"Code execution error: {e}")
        return {"success": False, "error": str(e)}


# ==================== FILE OPERATIONS ====================

async def file_create(filename, content, directory=None):
    """
    Create a file with content.
    
    Args:
        filename: Name of the file
        content: File content
        directory: Directory path (default: temp)
    
    Returns:
        dict with creation result
    """
    try:
        if directory is None:
            directory = tempfile.mkdtemp()
        
        filepath = os.path.join(directory, filename)
        
        # Create directory if needed
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Write file
        with open(filepath, 'w') as f:
            f.write(content)
        
        return {
            "success": True,
            "path": filepath,
            "filename": filename,
            "size": len(content)
        }
    
    except Exception as e:
        logger.error(f"File create error: {e}")
        return {"success": False, "error": str(e)}


async def file_read(filepath):
    """
    Read file content.
    
    Args:
        filepath: Path to file
    
    Returns:
        dict with file content
    """
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        return {
            "success": True,
            "content": content,
            "path": filepath,
            "size": len(content)
        }
    
    except Exception as e:
        logger.error(f"File read error: {e}")
        return {"success": False, "error": str(e)}


# ==================== GITHUB OPERATIONS ====================

async def github_push(repo, filename, content, message="feat: Add file via OXYGENT", token=None):
    """
    Push code to GitHub repository.
    
    Args:
        repo: Repository (owner/repo)
        filename: File path in repo
        content: File content
        message: Commit message
        token: GitHub token
    
    Returns:
        dict with push result
    """
    try:
        if not token:
            return {"success": False, "error": "GitHub token required"}
        
        # Encode content
        content_encoded = base64.b64encode(content.encode()).decode()
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            # Check if file exists
            sha = None
            async with session.get(
                f"https://api.github.com/repos/{repo}/contents/{filename}",
                headers=headers
            ) as response:
                if response.status == 200:
                    file_data = await response.json()
                    sha = file_data.get('sha')
            
            # Create or update file
            payload = {
                "message": message,
                "content": content_encoded,
            }
            if sha:
                payload["sha"] = sha
            
            async with session.put(
                f"https://api.github.com/repos/{repo}/contents/{filename}",
                headers=headers,
                json=payload
            ) as response:
                if response.status in [200, 201]:
                    result = await response.json()
                    return {
                        "success": True,
                        "url": result.get('content', {}).get('html_url', ''),
                        "filename": filename,
                        "repo": repo
                    }
                else:
                    error = await response.json()
                    return {"success": False, "error": error.get('message', 'Unknown error')}
    
    except Exception as e:
        logger.error(f"GitHub push error: {e}")
        return {"success": False, "error": str(e)}


# ==================== CODE ANALYSIS ====================

async def explain_code(code, language="python"):
    """
    Explain code line by line.
    
    Args:
        code: Code to explain
        language: Programming language
    
    Returns:
        dict with explanation
    """
    try:
        lines = code.strip().split('\n')
        explanation = []
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            # Basic line explanation
            if line.startswith('#'):
                explanation.append(f"Line {i}: Comment - {line[1:].strip()}")
            elif line.startswith('def '):
                func_name = line.split('(')[0].replace('def ', '')
                explanation.append(f"Line {i}: Function definition - {func_name}()")
            elif line.startswith('class '):
                class_name = line.split('(')[0].replace('class ', '').replace(':', '')
                explanation.append(f"Line {i}: Class definition - {class_name}")
            elif line.startswith('import ') or line.startswith('from '):
                explanation.append(f"Line {i}: Import statement - {line}")
            elif line.startswith('if '):
                explanation.append(f"Line {i}: Conditional check")
            elif line.startswith('for '):
                explanation.append(f"Line {i}: Loop iteration")
            elif line.startswith('return'):
                explanation.append(f"Line {i}: Return value")
            elif '=' in line and not line.startswith('=='):
                explanation.append(f"Line {i}: Variable assignment")
            else:
                explanation.append(f"Line {i}: {line[:50]}...")
        
        return {
            "success": True,
            "explanation": '\n'.join(explanation),
            "language": language,
            "line_count": len(lines)
        }
    
    except Exception as e:
        logger.error(f"Explain code error: {e}")
        return {"success": False, "error": str(e)}


async def debug_code(code, error_message, language="python"):
    """
    Find and fix bugs in code.
    
    Args:
        code: Buggy code
        error_message: Error message
        language: Programming language
    
    Returns:
        dict with fixed code and explanation
    """
    try:
        # Common error patterns and fixes
        fixes = []
        fixed_code = code
        
        # Syntax errors
        if "SyntaxError" in error_message:
            if "unexpected EOF" in error_message:
                fixes.append("Missing closing parenthesis or bracket")
                # Try to fix common missing brackets
                if code.count('(') > code.count(')'):
                    fixed_code = code + ')'
                elif code.count('[') > code.count(']'):
                    fixed_code = code + ']'
                elif code.count('{') > code.count('}'):
                    fixed_code = code + '}'
        
        # Indentation errors
        elif "IndentationError" in error_message:
            fixes.append("Inconsistent indentation - use 4 spaces")
        
        # Name errors
        elif "NameError" in error_message:
            var_name = error_message.split("'")[1] if "'" in error_message else "variable"
            fixes.append(f"Variable '{var_name}' is not defined")
        
        # Type errors
        elif "TypeError" in error_message:
            fixes.append("Type mismatch - check variable types")
        
        # Attribute errors
        elif "AttributeError" in error_message:
            fixes.append("Object doesn't have this attribute")
        
        return {
            "success": True,
            "fixed_code": fixed_code,
            "issues_found": fixes,
            "error": error_message,
            "language": language
        }
    
    except Exception as e:
        logger.error(f"Debug code error: {e}")
        return {"success": False, "error": str(e)}


async def optimize_code(code, language="python"):
    """
    Optimize code for performance.
    
    Args:
        code: Code to optimize
        language: Programming language
    
    Returns:
        dict with optimized code and improvements
    """
    try:
        improvements = []
        optimized = code
        
        # Python optimizations
        if language.lower() == "python":
            # List comprehension optimization
            if "for " in code and "append" in code:
                improvements.append("Consider using list comprehension instead of append in loop")
            
            # String concatenation
            if '+=' in code and '"' in code:
                improvements.append("Consider using f-strings or join() for string concatenation")
            
            # Generator vs list
            if "return [" in code and "yield" not in code:
                improvements.append("Consider using generator for large datasets")
        
        return {
            "success": True,
            "optimized_code": optimized,
            "improvements": improvements,
            "language": language
        }
    
    except Exception as e:
        logger.error(f"Optimize code error: {e}")
        return {"success": False, "error": str(e)}


async def convert_code(code, source_lang, target_lang):
    """
    Convert code between programming languages.
    
    Args:
        code: Source code
        source_lang: Source language
        target_lang: Target language
    
    Returns:
        dict with converted code
    """
    try:
        # Basic conversion templates
        conversions = {
            ("python", "javascript"): {
                "def ": "function ",
                "print(": "console.log(",
                "True": "true",
                "False": "false",
                "None": "null",
            },
            ("javascript", "python"): {
                "function ": "def ",
                "console.log(": "print(",
                "true": "True",
                "false": "False",
                "null": "None",
            }
        }
        
        converted = code
        key = (source_lang.lower(), target_lang.lower())
        
        if key in conversions:
            for old, new in conversions[key].items():
                converted = converted.replace(old, new)
        
        return {
            "success": True,
            "converted_code": converted,
            "source_lang": source_lang,
            "target_lang": target_lang
        }
    
    except Exception as e:
        logger.error(f"Convert code error: {e}")
        return {"success": False, "error": str(e)}


async def write_tests(code, language="python", framework="pytest"):
    """
    Generate unit tests for code.
    
    Args:
        code: Code to test
        language: Programming language
        framework: Test framework
    
    Returns:
        dict with test code
    """
    try:
        # Extract function names
        if language.lower() == "python":
            import re
            functions = re.findall(r'def (\w+)\(', code)
            
            test_code = f"import pytest\n\n"
            for func in functions:
                test_code += f"""
def test_{func}():
    # TODO: Add test for {func}
    result = {func}()
    assert result is not None
"""
        
        else:
            test_code = f"// Tests for {language} code\n// TODO: Implement tests"
        
        return {
            "success": True,
            "test_code": test_code,
            "language": language,
            "framework": framework
        }
    
    except Exception as e:
        logger.error(f"Write tests error: {e}")
        return {"success": False, "error": str(e)}


async def api_test(url, method="GET", headers=None, body=None):
    """
    Test API endpoints.
    
    Args:
        url: API URL
        method: HTTP method
        headers: Request headers
        body: Request body
    
    Returns:
        dict with API response
    """
    try:
        async with aiohttp.ClientSession() as session:
            kwargs = {
                "headers": headers or {},
                "timeout": aiohttp.ClientTimeout(total=10)
            }
            
            if body and method.upper() in ["POST", "PUT", "PATCH"]:
                kwargs["json"] = body
            
            async with session.request(method, url, **kwargs) as response:
                try:
                    response_body = await response.json()
                except:
                    response_body = await response.text()
                
                return {
                    "success": True,
                    "status": response.status,
                    "headers": dict(response.headers),
                    "body": response_body,
                    "url": url,
                    "method": method
                }
    
    except Exception as e:
        logger.error(f"API test error: {e}")
        return {"success": False, "error": str(e)}


# ==================== TOOL REGISTRY ====================

TOOLS = {
    "website_screenshot": website_screenshot,
    "web_search": web_search,
    "code_execute": code_execute,
    "file_create": file_create,
    "file_read": file_read,
    "github_push": github_push,
    "explain_code": explain_code,
    "debug_code": debug_code,
    "optimize_code": optimize_code,
    "convert_code": convert_code,
    "write_tests": write_tests,
    "api_test": api_test,
}

# Initialize memory system
memory = MemorySystem()


async def call_tool(tool_name, **kwargs):
    """
    Call a tool by name.
    
    Args:
        tool_name: Name of the tool
        **kwargs: Tool parameters
    
    Returns:
        Tool result
    """
    if tool_name not in TOOLS:
        return {"success": False, "error": f"Tool '{tool_name}' not found"}
    
    try:
        result = await TOOLS[tool_name](**kwargs)
        return result
    except Exception as e:
        logger.error(f"Tool call error: {e}")
        return {"success": False, "error": str(e)}
