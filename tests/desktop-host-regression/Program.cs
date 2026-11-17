using System.Collections.Concurrent;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using SodaPromptHub.Desktop;

// Run in an isolated environment: this fixture owns the Desktop Core port 8777.
// A non-product health response ensures the test never opens a real browser.
var listener = new TcpListener(IPAddress.Loopback, 8777);
listener.Start();
var server = Task.Run(async () =>
{
    using var client = await listener.AcceptTcpClientAsync();
    var stream = client.GetStream();
    var buffer = new byte[4096];
    await stream.ReadAsync(buffer);
    await Task.Delay(150);
    const string body = "{\"service\":\"regression-test-not-prompt-hub\"}";
    var response = Encoding.UTF8.GetBytes($"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {body.Length}\r\nConnection: close\r\n\r\n{body}");
    await stream.WriteAsync(response);
});
var context = new PumpContext();
using var finished = new ManualResetEventSlim();
Exception? failure = null;
var rejectedWrongService = false;
var ui = new Thread(() =>
{
    SynchronizationContext.SetSynchronizationContext(context);
    using var host = new DesktopHost();
    try
    {
        // Legacy fallback lets this same fixture prove red before the fix.
        var method = typeof(DesktopHost).GetMethod("OpenWorkspaceAsync", BindingFlags.Instance | BindingFlags.NonPublic)
            ?? typeof(DesktopHost).GetMethod("OpenWorkspace", BindingFlags.Instance | BindingFlags.NonPublic)!;
        if (method.Invoke(host, null) is Task pending)
        {
            while (!pending.IsCompleted) context.PumpOnce();
            pending.GetAwaiter().GetResult();
        }
    }
    catch (Exception error)
    {
        var actual = error is TargetInvocationException invocation ? invocation.InnerException! : error;
        rejectedWrongService = actual is InvalidOperationException && actual.Message.Contains("Core");
        if (!rejectedWrongService) failure = actual;
    }
    finally { finished.Set(); }
}) { IsBackground = true };
ui.Start();
if (!finished.Wait(TimeSpan.FromSeconds(4)))
{
    Console.Error.WriteLine($"FAIL: UI thread deadlocked while opening workspace; queued continuations={context.Queued}.");
    listener.Stop();
    return 1;
}
listener.Stop();
await server;
if (failure is not null || !rejectedWrongService)
{
    Console.Error.WriteLine($"FAIL: service identity guard changed: {failure}");
    return 1;
}
Console.WriteLine("PASS: UI context remains pumpable during delayed health check; wrong service is rejected without opening a browser.");
return 0;

sealed class PumpContext : SynchronizationContext
{
    private readonly BlockingCollection<Action> queue = new();
    internal int Queued => queue.Count;
    public override void Post(SendOrPostCallback callback, object? state) => queue.Add(() => callback(state));
    internal void PumpOnce() { if (queue.TryTake(out var action, 100)) action(); }
}
