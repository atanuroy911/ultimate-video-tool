# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for a security problem.

Report it privately through GitHub: on this repository, open **Security → Report a vulnerability**. Include what you found, how to reproduce it, and what an attacker could do with it.

We aim to reply within a week, and to publish a fix and an advisory once a fix is ready. We will credit you unless you ask us not to.

## Supported versions

Only the latest release receives security fixes.

## What is in scope

Ultimate Video Tool runs a local HTTP server, approves clients over the network, downloads models and runs AI assistants. We especially want to hear about:

- reaching the server's API or files without approval, or from another network
- path traversal or symlink escapes out of a project or data folder
- the MCP HTTP endpoint (`vt-mcp --http`) accepting requests without its token
- running commands or code through a crafted project, link, media file, theme (`.vttheme`) or AI answer
- leaking API keys, tokens or pairing codes

## Good practice for users

- Keep the server on a trusted network. Don't expose its port to the internet.
- A tunnel for the MCP HTTP endpoint makes your local tools reachable. Keep its token secret and close the tunnel when you are done.
- Only import links and media you have the right to use.
