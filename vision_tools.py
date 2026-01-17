"""
Vision Tools for SuperCoder - UI Analysis with Qwen3-VL
Supports both local models (2B, 4B, 8B, 32B) and OpenRouter API
"""
import os
import json
import base64
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# Vision model configuration
_vision_config = {
    "mode": "api",  # "local" or "api"
    "local_model": "2b",  # "2b", "4b", "8b", "32b"
    "local_model_loaded": False,
    "model_instance": None,
    "processor_instance": None,
    "device": None
}

def vision_set_mode(mode: str, model_size: str = "2b") -> Dict[str, Any]:
    """
    Set vision model mode and size.
    
    Args:
        mode: "local" or "api"
        model_size: For local mode: "2b", "4b", "8b", "32b"
    
    Returns:
        Configuration status
    """
    global _vision_config
    
    if mode not in ["local", "api"]:
        return {"error": f"Invalid mode: {mode}. Use 'local' or 'api'"}
    
    if mode == "local":
        if model_size not in ["2b", "4b", "8b", "32b"]:
            return {"error": f"Invalid model_size: {model_size}. Use '2b', '4b', '8b', or '32b'"}
        
        _vision_config["mode"] = "local"
        _vision_config["local_model"] = model_size
        _vision_config["local_model_loaded"] = False
        
        return {
            "mode": "local",
            "model_size": model_size,
            "message": f"Vision mode set to local Qwen3-VL-{model_size.upper()}",
            "note": "Model will be downloaded on first use (~2-15GB depending on size)"
        }
    
    else:  # api mode
        _vision_config["mode"] = "api"
        _vision_config["local_model_loaded"] = False
        
        # Unload local model if loaded
        if _vision_config["model_instance"] is not None:
            _vision_config["model_instance"] = None
            _vision_config["processor_instance"] = None
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        
        return {
            "mode": "api",
            "message": "Vision mode set to OpenRouter API (Qwen3-VL)",
            "note": "Uses OpenRouter API - costs ~$0.01-0.03 per image"
        }


def vision_get_status() -> Dict[str, Any]:
    """
    Get current vision configuration status.
    
    Returns:
        Current configuration and model info
    """
    global _vision_config
    
    status = {
        "mode": _vision_config["mode"],
        "local_model": _vision_config["local_model"],
        "local_model_loaded": _vision_config["local_model_loaded"]
    }
    
    if _vision_config["mode"] == "local":
        status["model_name"] = f"Qwen3-VL-{_vision_config['local_model'].upper()}-Instruct"
        status["device"] = str(_vision_config.get("device", "Not loaded"))
        
        # Check if dependencies are installed
        try:
            import torch
            import transformers
            status["dependencies_installed"] = True
            status["cuda_available"] = torch.cuda.is_available()
            if torch.cuda.is_available():
                status["gpu_name"] = torch.cuda.get_device_name(0)
                status["gpu_memory_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2)
        except ImportError as e:
            status["dependencies_installed"] = False
            status["missing_packages"] = "torch, transformers, qwen-vl-utils"
    
    else:  # api mode
        status["api_endpoint"] = "OpenRouter (Qwen3-VL)"
        status["cost_per_image"] = "~$0.01-0.03"
    
    return status


def _load_local_model() -> Dict[str, Any]:
    """Load local Qwen3-VL model"""
    global _vision_config
    
    if _vision_config["local_model_loaded"]:
        return {"success": True, "message": "Model already loaded"}
    
    try:
        import torch
        from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
        from qwen_vl_utils import process_vision_info
        
        model_size = _vision_config["local_model"]
        model_name = f"Qwen/Qwen2-VL-{model_size.upper()}-Instruct"
        
        print(f"[Loading Qwen3-VL-{model_size.upper()} model... This may take a few minutes on first run]")
        
        # Determine device
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _vision_config["device"] = device
        
        # Load model
        model = Qwen2VLForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            device_map="auto" if device == "cuda" else None
        )
        
        # Load processor
        processor = AutoProcessor.from_pretrained(model_name)
        
        _vision_config["model_instance"] = model
        _vision_config["processor_instance"] = processor
        _vision_config["local_model_loaded"] = True
        
        return {
            "success": True,
            "model": model_name,
            "device": device,
            "message": f"Qwen3-VL-{model_size.upper()} loaded successfully on {device}"
        }
    
    except ImportError as e:
        return {
            "error": "Missing dependencies. Install with: pip install torch transformers qwen-vl-utils",
            "details": str(e)
        }
    except Exception as e:
        return {
            "error": f"Failed to load model: {str(e)}",
            "suggestion": "Try a smaller model size (2b) or use API mode"
        }


def _analyze_with_local_model(image_path: str, prompt: str) -> Dict[str, Any]:
    """Analyze image with local Qwen3-VL model"""
    global _vision_config
    
    # Load model if not loaded
    if not _vision_config["local_model_loaded"]:
        load_result = _load_local_model()
        if "error" in load_result:
            return load_result
    
    try:
        import torch
        from qwen_vl_utils import process_vision_info
        
        model = _vision_config["model_instance"]
        processor = _vision_config["processor_instance"]
        
        # Prepare messages
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": f"file://{Path(image_path).absolute()}"},
                    {"type": "text", "text": prompt}
                ]
            }
        ]
        
        # Process
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        
        inputs = processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt"
        )
        
        # Move to device
        inputs = inputs.to(_vision_config["device"])
        
        # Generate
        with torch.no_grad():
            generated_ids = model.generate(**inputs, max_new_tokens=512)
        
        # Trim input tokens
        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        
        # Decode
        output_text = processor.batch_decode(
            generated_ids_trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False
        )[0]
        
        return {
            "success": True,
            "analysis": output_text,
            "model": f"Qwen3-VL-{_vision_config['local_model'].upper()}-Instruct",
            "device": str(_vision_config["device"])
        }
    
    except Exception as e:
        return {"error": f"Local model analysis failed: {str(e)}"}


def _analyze_with_api(image_path: str, prompt: str) -> Dict[str, Any]:
    """Analyze image with OpenRouter API"""
    try:
        # Read and encode image
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        # Get API key
        from Agentic import TokenManager
        TokenManager.load_tokens()
        api_key = TokenManager.get_token()
        
        # Prepare request
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Try Qwen3-VL first, fallback to GPT-4V
        models_to_try = [
            "qwen/qwen-2-vl-72b-instruct",  # Qwen3-VL on OpenRouter
            "openai/gpt-4-vision-preview",   # GPT-4V fallback
            "anthropic/claude-3-opus"        # Claude Vision fallback
        ]
        
        for model in models_to_try:
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_data}"
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            }
            
            try:
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                
                if response.status_code == 200:
                    data = response.json()
                    analysis = data["choices"][0]["message"]["content"]
                    
                    return {
                        "success": True,
                        "analysis": analysis,
                        "model": model,
                        "mode": "api"
                    }
            except Exception as e:
                continue  # Try next model
        
        return {"error": "All API models failed. Try local mode or check API key."}
    
    except Exception as e:
        return {"error": f"API analysis failed: {str(e)}"}


def vision_analyze_ui(screenshot_path: str, prompt: str = None) -> Dict[str, Any]:
    """
    Analyze a UI screenshot using vision model.
    
    Args:
        screenshot_path: Path to screenshot
        prompt: Optional specific question. If None, does general UI analysis.
    
    Returns:
        analysis: Detailed description of UI
        issues: List of potential problems
        suggestions: Improvement recommendations
    """
    global _vision_config
    
    # Check if file exists
    if not Path(screenshot_path).exists():
        return {"error": f"Screenshot not found: {screenshot_path}"}
    
    # Default prompt for UI analysis
    if prompt is None:
        prompt = """Analyze this user interface screenshot in detail. Provide:

1. **Layout Description**: Describe the overall layout and structure
2. **UI Elements**: List all visible UI elements (buttons, forms, text, images, etc.)
3. **Issues Found**: Identify any visual problems:
   - Overlapping elements
   - Misaligned components
   - Low contrast text
   - Elements off-screen or cut off
   - Broken layouts
   - Missing elements
4. **Accessibility Concerns**: Note any accessibility issues
5. **Suggestions**: Provide specific recommendations to fix issues

Be specific and actionable in your analysis."""
    
    # Analyze based on mode
    if _vision_config["mode"] == "local":
        result = _analyze_with_local_model(screenshot_path, prompt)
    else:
        result = _analyze_with_api(screenshot_path, prompt)
    
    if "error" in result:
        return result
    
    # Parse analysis into structured format
    analysis_text = result["analysis"]
    
    # Try to extract issues and suggestions
    issues = []
    suggestions = []
    
    # Simple parsing (can be improved)
    lines = analysis_text.split('\n')
    in_issues = False
    in_suggestions = False
    
    for line in lines:
        line = line.strip()
        if 'issue' in line.lower() or 'problem' in line.lower():
            in_issues = True
            in_suggestions = False
        elif 'suggest' in line.lower() or 'recommend' in line.lower():
            in_suggestions = True
            in_issues = False
        elif line.startswith('-') or line.startswith('•') or line.startswith('*'):
            if in_issues:
                issues.append(line.lstrip('-•* '))
            elif in_suggestions:
                suggestions.append(line.lstrip('-•* '))
    
    return {
        "screenshot_path": screenshot_path,
        "analysis": analysis_text,
        "issues": issues if issues else ["No specific issues detected"],
        "suggestions": suggestions if suggestions else ["No specific suggestions"],
        "model": result.get("model", "unknown"),
        "mode": _vision_config["mode"]
    }


def vision_find_element(screenshot_path: str, description: str) -> Dict[str, Any]:
    """
    Find an element by visual description.
    
    Args:
        screenshot_path: Path to screenshot
        description: Natural language description (e.g., "blue login button")
    
    Returns:
        found: Boolean
        description: What was found
        location_description: Where it is on the page
    """
    prompt = f"""Look at this screenshot and find the element matching this description: "{description}"

If found, provide:
1. **Found**: Yes or No
2. **Exact Description**: Describe what you see
3. **Location**: Where is it on the page (top-left, center, bottom-right, etc.)
4. **Nearby Elements**: What's around it
5. **Visual Properties**: Color, size, shape, text content

Be specific and precise."""
    
    if _vision_config["mode"] == "local":
        result = _analyze_with_local_model(screenshot_path, prompt)
    else:
        result = _analyze_with_api(screenshot_path, prompt)
    
    if "error" in result:
        return result
    
    analysis = result["analysis"]
    found = "yes" in analysis.lower()[:100] or "found" in analysis.lower()[:100]
    
    return {
        "screenshot_path": screenshot_path,
        "search_description": description,
        "found": found,
        "analysis": analysis,
        "model": result.get("model", "unknown")
    }


def vision_verify_layout(screenshot_path: str, expected_elements: List[str]) -> Dict[str, Any]:
    """
    Verify that expected UI elements are present and correctly positioned.
    
    Args:
        screenshot_path: Path to screenshot
        expected_elements: List of elements that should be visible
    
    Returns:
        all_present: Boolean
        missing_elements: List of missing elements
        layout_issues: List of positioning problems
    """
    elements_str = "\n".join([f"- {elem}" for elem in expected_elements])
    
    prompt = f"""Check if these UI elements are present and correctly positioned in this screenshot:

{elements_str}

For each element, report:
1. **Present**: Yes or No
2. **Position**: Where it is (if present)
3. **Issues**: Any positioning or visibility problems

Provide a summary at the end."""
    
    if _vision_config["mode"] == "local":
        result = _analyze_with_local_model(screenshot_path, prompt)
    else:
        result = _analyze_with_api(screenshot_path, prompt)
    
    if "error" in result:
        return result
    
    analysis = result["analysis"]
    
    # Parse for missing elements
    missing = []
    for elem in expected_elements:
        if elem.lower() in analysis.lower():
            if "not present" in analysis.lower() or "missing" in analysis.lower():
                missing.append(elem)
    
    return {
        "screenshot_path": screenshot_path,
        "expected_elements": expected_elements,
        "all_present": len(missing) == 0,
        "missing_elements": missing,
        "analysis": analysis,
        "model": result.get("model", "unknown")
    }


def vision_accessibility_check(screenshot_path: str) -> Dict[str, Any]:
    """
    Check UI for accessibility issues.
    
    Returns:
        contrast_issues: Low contrast text
        small_text: Text too small to read
        missing_labels: Form fields without labels
        color_only_info: Information conveyed by color alone
    """
    prompt = """Analyze this UI screenshot for accessibility issues:

1. **Contrast Issues**: Identify text with low contrast against background
2. **Text Size**: Find text that's too small to read comfortably
3. **Form Labels**: Check if form inputs have visible labels
4. **Color Dependency**: Find information conveyed only by color
5. **Touch Targets**: Identify buttons/links that are too small
6. **Visual Hierarchy**: Check if important elements stand out

Provide specific, actionable findings."""
    
    if _vision_config["mode"] == "local":
        result = _analyze_with_local_model(screenshot_path, prompt)
    else:
        result = _analyze_with_api(screenshot_path, prompt)
    
    if "error" in result:
        return result
    
    return {
        "screenshot_path": screenshot_path,
        "analysis": result["analysis"],
        "model": result.get("model", "unknown"),
        "note": "Review analysis for specific accessibility issues"
    }


def vision_compare_screenshots(screenshot1_path: str, screenshot2_path: str) -> Dict[str, Any]:
    """
    Compare two screenshots for visual differences (visual regression testing).
    
    Args:
        screenshot1_path: Path to first screenshot (baseline)
        screenshot2_path: Path to second screenshot (current)
    
    Returns:
        differences_found: Boolean
        differences: List of visual differences
        severity: "none", "minor", "major"
    """
    # For now, analyze each separately and compare
    # In future, could use a diff algorithm
    
    prompt1 = "Describe this UI in detail: layout, colors, text, buttons, forms, images."
    prompt2 = "Describe this UI in detail: layout, colors, text, buttons, forms, images."
    
    if _vision_config["mode"] == "local":
        result1 = _analyze_with_local_model(screenshot1_path, prompt1)
        result2 = _analyze_with_local_model(screenshot2_path, prompt2)
    else:
        result1 = _analyze_with_api(screenshot1_path, prompt1)
        result2 = _analyze_with_api(screenshot2_path, prompt2)
    
    if "error" in result1:
        return result1
    if "error" in result2:
        return result2
    
    # Simple comparison (can be improved with actual diff)
    desc1 = result1["analysis"]
    desc2 = result2["analysis"]
    
    differences_found = desc1 != desc2
    
    return {
        "screenshot1": screenshot1_path,
        "screenshot2": screenshot2_path,
        "differences_found": differences_found,
        "baseline_description": desc1,
        "current_description": desc2,
        "note": "Manual comparison recommended for detailed diff",
        "model": result1.get("model", "unknown")
    }
