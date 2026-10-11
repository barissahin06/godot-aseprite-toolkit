import tempfile
import os
import dotenv
import shutil
from pathlib import Path
from .runtime import run_native, checkpoint, workspace_lock, publish

_ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
dotenv.load_dotenv(dotenv_path=_ENV_PATH)


def lua_escape(s: str) -> str:
    """Escape a string for safe embedding inside a Lua double-quoted string literal."""
    return (
        s.replace("\\", "\\\\")
         .replace('"', '\\"')
         .replace("\n", "\\n")
         .replace("\r", "\\r")
         .replace("\0", "\\0")
    )


def reject_traversal(path: str) -> str | None:
    """Reject parent-directory traversal in a user-supplied path.

    Returns an error message string when the path contains a `..`
    component, or None when the path looks safe.

    The check works on normalized path components, so it does not
    false-positive on filenames like `foo..bar.aseprite` (the previous
    `'..' in path` substring check did). Absolute paths and tilde
    expansion are not rejected here: this function targets traversal
    only, not access scoping.
    """
    parts = os.path.normpath(path).replace("\\", "/").split("/")
    if ".." in parts:
        return "Invalid filename: parent directory traversal not allowed"
    return None


class AsepriteCommand:
    """Helper class for running Aseprite commands."""
    
    @staticmethod
    def run_command(args):
        """Run an Aseprite command with proper error handling.
        
        Args:
            args: List of command arguments
            
        Returns:
            tuple: (success, output) where success is a boolean and output is the command output
        """
        try:
            cmd = [os.getenv('ASEPRITE_PATH', 'aseprite')] + args
            result = run_native(cmd[0], cmd[1:], Path.cwd(), int(os.getenv('ASEPRITE_TIMEOUT', '120')))
            return True, result['log']
        except (RuntimeError, OSError, ValueError) as e:
            return False, str(e)
    
    @staticmethod
    def execute_lua_script(script_content, filename=None):
        """Execute a Lua script in Aseprite.
        
        Args:
            script_content: Lua script code to execute
            filename: Optional filename to open before executing script
            
        Returns:
            tuple: (success, output)
        """
        source = Path(filename).resolve() if filename and os.path.isfile(filename) else None
        native = source is not None and source.suffix.lower() in ('.aseprite', '.ase')
        configured = Path(os.environ.get('ART_REPO', Path.cwd())).resolve()
        workspace = configured if source is None or source.is_relative_to(configured) else source.parent
        with workspace_lock(workspace), tempfile.TemporaryDirectory(prefix='ase-edit-') as folder:
            working = Path(folder) / ('working' + source.suffix) if native else source
            script = script_content
            if native:
                shutil.copyfile(source, working)
                for spelling in {str(source), source.as_posix(), str(filename)}:
                    script = script.replace(lua_escape(spelling), lua_escape(working.as_posix()))
            script_path = Path(folder) / 'operation.lua'
            script_path.write_text(script, encoding='utf-8')
            args = ['--batch', *([str(working)] if working else []), '--script', str(script_path)]
            success, output = AsepriteCommand.run_command(args)
            if success and native and working.read_bytes() != source.read_bytes():
                content = working.read_bytes()
                if len(content) < 128 or content[4:6] != b'\xe0\xa5':
                    return False, 'Invalid native output; original preserved'
                checkpoint(workspace, [source.relative_to(workspace).as_posix()], 'before Aseprite edit')
                publish(workspace, {source: content})
            if native:
                output = output.replace(working.as_posix(), str(filename)).replace(str(working), str(filename))
            return success, output

    @staticmethod
    def execute_lua_script_checked(script_content, filename=None):
        """Execute a Lua script and surface in-script errors.

        Scripts using this helper signal failure by printing a line
        starting with "ERROR:" (batch-mode scripts cannot affect the
        process exit code from Lua).

        Returns:
            tuple: (success, output) where output is the error message
            when an ERROR: line was printed, or the raw stdout otherwise.
        """
        success, output = AsepriteCommand.execute_lua_script(script_content, filename)
        if not success:
            return False, output
        for line in output.splitlines():
            if line.startswith("ERROR:"):
                return False, line[len("ERROR:"):]
        return True, output
