# Worminal

[Xenorepo on GitHub](https://github.com/flintwinters/xenorepo)

Worminal provides an ephemeral interactive Linux shell in a browser. It intentionally accepts shell
connections only from the runtime host's loopback interface; it is not yet suitable for remote
deployment.

Use the Xenorepo cockpit for every lifecycle operation:

```console
uv run manage.py worminal check
uv run manage.py worminal test
uv run manage.py worminal ui-check
uv run manage.py worminal serve
```

The app consumes the enclosing Xenorepo's Monotools version. Each browser connection owns one shell
process group, which is terminated when the connection closes.
