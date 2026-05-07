# Setup Prompt

Use this prompt when the user asks to install or refresh xanad-assistant in the 
active repository.

Target workspace: {{WORKSPACE_NAME}}
Selected profile: {{XANAD_PROFILE}}

1. Run `xanad-assistant.py inspect` with the active workspace and package root.
2. Review warnings or required questions with the user.
3. Prefer structured plan generation before any write-capable command.
