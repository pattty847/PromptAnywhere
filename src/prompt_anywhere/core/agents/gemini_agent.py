"""Gemini CLI agent implementation"""
import sys
import os
import tempfile
import subprocess
import shutil
import textwrap
from typing import Iterator, Optional
from prompt_anywhere.core.agents.base_agent import BaseAgent


class GeminiAgent(BaseAgent):
    """Gemini CLI agent implementation"""
    
    def __init__(self):
        """Initialize Gemini agent and check if CLI is available"""
        if not shutil.which('gemini') and not shutil.which('gemini.cmd'):
            raise FileNotFoundError(
                "Gemini CLI not found. Please install it first.\n"
                "Installation: npm install -g @google/gemini-cli"
            )
            
        self.sys_prompt = textwrap.dedent("""
            You are Gemini, a helpful assistant that can be spawned anywhere on the user's computer.
            Your role is to answer questions and assist with tasks as a helpful, concise AI.
            When context includes a screenshot or file, incorporate or describe its contents as relevant.
            Never include disclaimers about being AI unless the user requests it.
            Respect privacy and never offer unsolicited suggestions about security, updates, or personal info.
            Assume all prompts are from the owner at their Windows PC, possibly with clipboard content or images.
        """).strip()
    
    @property
    def name(self) -> str:
        """Agent name"""
        return "gemini"
    
    def send_prompt(self, prompt: str, context: Optional[dict] = None) -> Iterator[str]:
        """
        Send a prompt to Gemini CLI and stream the response
        
        Args:
            prompt: The user's prompt/question
            context: Optional context dict with 'image_bytes' key
            
        Yields:
            str: Chunks of the response as they arrive
        """
        tmp_path = None
        
        try:
            # Save screenshot to temporary file if provided
            image_bytes = context.get('image_bytes') if context else None
            cancel_event = context.get("cancel_event") if context else None
            if image_bytes:
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    tmp.write(image_bytes)
                    tmp_path = tmp.name
            
            # Build gemini command (use .cmd on Windows)
            gemini_cmd = 'gemini.cmd' if sys.platform == 'win32' else 'gemini'
            full_prompt = f"{self.sys_prompt}\n\n{prompt}" if self.sys_prompt else prompt
            if tmp_path:
                prompt_arg = f"{full_prompt} @{tmp_path}"
            else:
                prompt_arg = full_prompt
            if sys.platform == 'win32':
                cmd = ['cmd', '/c', gemini_cmd, '-p', prompt_arg]
            else:
                cmd = [gemini_cmd, '-p', prompt_arg]

            popen_kwargs = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "text": True,
                "bufsize": 1,
                "universal_newlines": True,
                "shell": False,
            }
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE
                popen_kwargs["startupinfo"] = startupinfo
                popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            # Run subprocess with streaming output
            process = subprocess.Popen(cmd, **popen_kwargs)
            
            # Stream output line by line
            for line in iter(process.stdout.readline, ''):
                if cancel_event is not None and cancel_event.is_set():
                    process.terminate()
                    process.wait()
                    return
                if line:
                    yield line
            
            # Wait for completion
            process.wait()
            
            if process.returncode != 0:
                error_msg = process.stderr.read()
                raise RuntimeError(f"Gemini CLI error: {error_msg}")
        
        except FileNotFoundError:
            raise FileNotFoundError("Gemini CLI not found. Please install it first.")
        except Exception as e:
            raise RuntimeError(str(e))
        finally:
            # Clean up temp file
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
