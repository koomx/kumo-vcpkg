import sys

if sys.platform.startswith('linux'):
    from .linux import install_binary, get_shell_files, render_env_lines
elif sys.platform == 'darwin':
    from .macos import install_binary, get_shell_files, render_env_lines
elif sys.platform in ('win32', 'cygwin', 'msys'):
    from .windows import install_binary, get_shell_files, render_env_lines, set_env_vars
else:
    raise RuntimeError('unsupported platform: ' + sys.platform)
