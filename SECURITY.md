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

## What the server accepts

- **A web page never may**, in any mode. A request is refused when its `Host` is not an address or a local name (a name that anyone on the internet could point at this computer), or when its `Origin` is another site's. The desktop apps, the helper, Claude Code and `curl` send no `Origin`, so they are not affected. Only a program that holds the server's key and sends it as `Authorization: Bearer <key>` skips this check, because a page cannot send that header.
- **This computer** needs nothing, as long as nothing forwarded the request (a tunnel or proxy on this computer counts as outside).
- **Other computers** send the server's key. That includes computers on the same Wi-Fi, because a private address is also a café's or a hotel's. The client's connect page asks for the key once and keeps it in a file only that user can read. The server window has **Copy key**.
- **Optional:** the switch "Computers on my network can connect without the key" (server window, or `vt server --trust-network`) lets private, link-local and Tailscale addresses in without the key. It is off by default. Turn it on only on a network you own.

Tests: `tests/test_server_webpage_guard.py` and `tests/test_server_auth.py`.

## Good practice for users

- Keep the server on a trusted network. Don't expose its port to the internet.
- A tunnel for the MCP HTTP endpoint makes your local tools reachable. Keep its token secret and close the tunnel when you are done.
- Only import links and media you have the right to use.
