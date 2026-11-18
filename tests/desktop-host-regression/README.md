# Windows Desktop UI-context regression

Run from the repository root, in an isolated Docker network (do not use host networking):

```sh
docker run --rm -v "$PWD:/src" -w /src mcr.microsoft.com/dotnet/sdk:8.0 \
  dotnet run --project tests/desktop-host-regression/DesktopHostRegression.csproj
```

This fixture links the real DesktopHost source and owns the Desktop Core port 8777.
It delays a deliberately non-product health response, invokes the workspace action on
a single-thread synchronization context, and verifies that callbacks remain pumpable
and the service-identity guard rejects the response without opening a browser.
The legacy synchronous method fallback lets the same fixture demonstrate the original
deadlock (four-second watchdog, exit 1). The asynchronous fix must exit 0.
