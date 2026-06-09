# Agent Notes

## Startup Script Parity

- Keep Windows and Linux startup scripts aligned by capability and user experience, not by identical implementation.
- For native startup, treat `start-native.ps1` and `start-native.sh` as counterparts. When changing flags, virtual environment handling, dependency installation, mihomo download, initial config generation, readiness checks, logging, environment variables, or failure messages in one script, review and update the other when the same capability applies.
- For Docker startup, treat `start.ps1` and `start.sh` as counterparts. Keep helper startup, Docker access preflight checks, Compose arguments, and actionable diagnostics functionally consistent.
- Respect platform differences. Use PowerShell-native behavior on Windows and Bash/Linux-native behavior on Linux. Examples: `.venv-windows` vs `.venv-linux`, `python`/`py -3` vs `python3`, Windows Docker named pipes and services vs Linux Unix sockets and socket groups.
- Startup scripts should be self-healing when it is safe. Detect incomplete or broken project-owned virtual environments, repair pip with `ensurepip` when possible, recreate the venv when needed, and remove incomplete venv directories after failed creation so the next run does not reuse a bad environment.
- Error messages should be based on detected system state. Avoid hardcoded assumptions such as a fixed Linux Docker group name; inspect the socket, context, endpoint, service, or current user/group state first, then print the most specific next step available.
