using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.NetworkInformation;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Windows.Forms;

[assembly: AssemblyTitle("Weibull 本地启动器")]
[assembly: AssemblyDescription("启动本地 Weibull 前后端并打开默认浏览器")]
[assembly: AssemblyCompany("weibull.work")]
[assembly: AssemblyProduct("Weibull Local Launcher")]
[assembly: AssemblyVersion("1.1.0.0")]

internal static class WeibullLocalLauncher
{
    private const string FrontendUrl = "http://127.0.0.1:3000";
    private const string BackendDocsUrl = "http://127.0.0.1:8001/docs";
    private const string BackendProbeUrl = "http://127.0.0.1:8001/openapi.json";
    private const int StartupTimeoutSeconds = 180;
    private static Form progressWindow;
    private static Label progressLabel;
    private static string launcherLog;
    private static bool quiet;

    [STAThread]
    private static void Main(string[] args)
    {
        quiet = HasArgument(args, "--no-browser");
        Application.EnableVisualStyles();
        bool createdNew;
        using (var mutex = new Mutex(true, "Local\\WeibullLocalLauncher", out createdNew))
        {
            if (!createdNew)
            {
                return;
            }

            try
            {
                string projectRoot = FindProjectRoot(AppDomain.CurrentDomain.BaseDirectory);
                if (projectRoot == null)
                {
                    projectRoot = FindConfiguredProjectRoot();
                }
                if (projectRoot == null)
                {
                    ShowError("没有找到 Weibull 项目目录。请确认项目仍位于 D:\\weibull，或设置 WEIBULL_PROJECT_ROOT 环境变量。");
                    return;
                }

                string logDirectory = Path.Combine(projectRoot, "logs");
                Directory.CreateDirectory(logDirectory);
                launcherLog = Path.Combine(logDirectory, "local-launcher.log");
                SetStatus("正在检查本地调试环境…");

                bool backendReady = IsBackendReady();
                bool frontendReady = IsFrontendReady();

                if (!backendReady)
                {
                    RequireFreePort(8001);
                    ToolCommand python = ResolvePython(projectRoot);
                    if (python == null)
                    {
                        ShowError("没有找到可用的 Python。请安装 Python，或在项目中创建 .venv/venv 虚拟环境。\n\n项目目录：" + projectRoot);
                        return;
                    }

                    SetStatus("正在启动 Python 后端（自动重载）…");
                    StartHiddenCommand(
                        python.Executable,
                        JoinArguments(python.ArgumentPrefix, "-m uvicorn main:app --host 127.0.0.1 --port 8001 --reload"),
                        Path.Combine(projectRoot, "python"),
                        Path.Combine(logDirectory, "local-launcher-backend.log"));
                }

                if (!frontendReady)
                {
                    RequireFreePort(3000);
                    string npm = ResolveNpm();
                    if (npm == null)
                    {
                        ShowError("没有找到 npm.cmd。请先安装 Node.js，并确认 npm 已加入 PATH。\n\n项目目录：" + projectRoot);
                        return;
                    }

                    if (!File.Exists(Path.Combine(projectRoot, "node_modules", "next", "dist", "bin", "next")))
                    {
                        throw new InvalidOperationException("项目缺少前端依赖，请先在项目目录执行一次 npm install。");
                    }
                    SetStatus("正在启动 Next.js 开发服务…首次编译可能需要一些时间。");
                    StartHiddenCommand(
                        npm,
                        "run dev -- --hostname 127.0.0.1 --port 3000",
                        projectRoot,
                        Path.Combine(logDirectory, "local-launcher-frontend.log"));
                }

                DateTime deadline = DateTime.UtcNow.AddSeconds(StartupTimeoutSeconds);
                while (DateTime.UtcNow < deadline)
                {
                    backendReady = IsBackendReady();
                    frontendReady = IsFrontendReady();
                    SetStatus("后端：" + (backendReady ? "已就绪" : "启动中") +
                        "    前端：" + (frontendReady ? "已就绪" : "启动 / 编译中") +
                        "\n就绪后自动打开应用与 API 调试页面。");
                    if (backendReady && frontendReady)
                    {
                        SetStatus("调试环境已就绪。");
                        if (!quiet)
                        {
                            Process.Start(new ProcessStartInfo(FrontendUrl) { UseShellExecute = true });
                            Process.Start(new ProcessStartInfo(BackendDocsUrl) { UseShellExecute = true });
                        }
                        return;
                    }

                    Thread.Sleep(500);
                }

                var missing = new StringBuilder();
                if (!backendReady)
                {
                    missing.AppendLine("- 后端 http://localhost:8001 未就绪");
                }
                if (!frontendReady)
                {
                    missing.AppendLine("- 前端 http://localhost:3000 未就绪");
                }

                ShowError(
                    "本地环境在 180 秒内未完全启动：\n" + missing +
                    "\n请查看日志目录：\n" + logDirectory);
            }
            catch (Exception exception)
            {
                ShowError("启动失败：\n" + exception.Message);
            }
            finally
            {
                if (progressWindow != null) progressWindow.Dispose();
            }
        }
    }

    private static void SetStatus(string message)
    {
        if (launcherLog != null)
            File.AppendAllText(launcherLog, DateTime.Now.ToString("s") + " " + message.Replace("\n", " ") + Environment.NewLine, Encoding.UTF8);
        if (quiet) return;
        if (progressWindow == null)
        {
            progressWindow = new Form { Text = "Weibull 调试启动器", Width = 530, Height = 150,
                StartPosition = FormStartPosition.CenterScreen, FormBorderStyle = FormBorderStyle.FixedDialog,
                MaximizeBox = false, MinimizeBox = true, ControlBox = false };
            progressLabel = new Label { Dock = DockStyle.Fill, Padding = new Padding(20), AutoSize = false };
            progressWindow.Controls.Add(progressLabel);
            progressWindow.Show();
        }
        progressLabel.Text = message;
        Application.DoEvents();
    }

    private static void RequireFreePort(int port)
    {
        foreach (var endpoint in IPGlobalProperties.GetIPGlobalProperties().GetActiveTcpListeners())
        {
            if (endpoint.Port == port)
                throw new InvalidOperationException("端口 " + port + " 已被其他或尚未就绪的服务占用。请检查该服务后重试；启动器不会结束其他程序。");
        }
    }

    private static string FindProjectRoot(string startDirectory)
    {
        var current = new DirectoryInfo(startDirectory);
        for (int depth = 0; current != null && depth < 6; depth++, current = current.Parent)
        {
            if (File.Exists(Path.Combine(current.FullName, "package.json")) &&
                File.Exists(Path.Combine(current.FullName, "python", "main.py")))
            {
                return current.FullName;
            }
        }
        return null;
    }

    private static string FindConfiguredProjectRoot()
    {
        string[] candidates =
        {
            Environment.GetEnvironmentVariable("WEIBULL_PROJECT_ROOT"),
            @"D:\weibull"
        };

        foreach (string candidate in candidates)
        {
            if (!string.IsNullOrWhiteSpace(candidate) &&
                File.Exists(Path.Combine(candidate, "package.json")) &&
                File.Exists(Path.Combine(candidate, "python", "main.py")))
            {
                return Path.GetFullPath(candidate);
            }
        }

        return null;
    }

    private static bool IsBackendReady()
    {
        return ResponseContains(BackendProbeUrl, "\"/calculate\"");
    }

    private static bool IsFrontendReady()
    {
        return ResponseContains(FrontendUrl, "Weibull Calculator");
    }

    private static bool ResponseContains(string url, string expectedText)
    {
        try
        {
            var request = (HttpWebRequest)WebRequest.Create(url);
            request.Timeout = 1000;
            request.ReadWriteTimeout = 1000;
            request.UserAgent = "WeibullLocalLauncher/1.0";
            using (var response = (HttpWebResponse)request.GetResponse())
            using (var reader = new StreamReader(response.GetResponseStream()))
            {
                return reader.ReadToEnd().IndexOf(expectedText, StringComparison.OrdinalIgnoreCase) >= 0;
            }
        }
        catch
        {
            return false;
        }
    }

    private static ToolCommand ResolvePython(string projectRoot)
    {
        string[] localCandidates =
        {
            Path.Combine(projectRoot, "python", ".venv", "Scripts", "python.exe"),
            Path.Combine(projectRoot, ".venv", "Scripts", "python.exe"),
            Path.Combine(projectRoot, "venv", "Scripts", "python.exe"),
            Path.Combine(projectRoot, "python", "venv", "Scripts", "python.exe")
        };

        foreach (string candidate in localCandidates)
        {
            if (File.Exists(candidate))
            {
                return new ToolCommand(candidate, null);
            }
        }

        string python = FindOnPath("python.exe", true);
        if (python != null)
        {
            return new ToolCommand(python, null);
        }

        string py = FindOnPath("py.exe");
        if (py != null)
        {
            return new ToolCommand(py, "-3");
        }

        return null;
    }

    private static string ResolveNpm()
    {
        string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string programFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        string programFilesX86 = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86);
        string appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
        string[] candidates =
        {
            Path.Combine(localAppData, "hermes", "node", "npm.cmd"),
            Path.Combine(programFiles, "nodejs", "npm.cmd"),
            Path.Combine(programFilesX86, "nodejs", "npm.cmd"),
            Path.Combine(appData, "npm", "npm.cmd")
        };

        foreach (string candidate in candidates)
        {
            if (File.Exists(candidate))
            {
                return candidate;
            }
        }

        return FindOnPath("npm.cmd");
    }

    private static string FindOnPath(string fileName)
    {
        return FindOnPath(fileName, false);
    }

    private static string FindOnPath(string fileName, bool skipWindowsApps)
    {
        string pathValue = Environment.GetEnvironmentVariable("PATH") ?? string.Empty;
        foreach (string rawDirectory in pathValue.Split(Path.PathSeparator))
        {
            string directory = rawDirectory.Trim().Trim('"');
            if (directory.Length == 0 || (skipWindowsApps && directory.IndexOf("WindowsApps", StringComparison.OrdinalIgnoreCase) >= 0))
            {
                continue;
            }

            try
            {
                string candidate = Path.Combine(directory, fileName);
                if (File.Exists(candidate))
                {
                    return candidate;
                }
            }
            catch
            {
                // Ignore malformed PATH entries and continue looking.
            }
        }
        return null;
    }

    private static void StartHiddenCommand(string executable, string arguments, string workingDirectory, string logPath)
    {
        File.AppendAllText(
            logPath,
            Environment.NewLine + "=== " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " ===" + Environment.NewLine,
            Encoding.UTF8);

        string command = "\"\"" + executable + "\"";
        if (!string.IsNullOrWhiteSpace(arguments))
        {
            command += " " + arguments;
        }
        command += " >> \"" + logPath + "\" 2>&1\"";

        var startInfo = new ProcessStartInfo
        {
            FileName = Environment.GetEnvironmentVariable("ComSpec") ?? "cmd.exe",
            Arguments = "/d /s /c " + command,
            WorkingDirectory = workingDirectory,
            UseShellExecute = false,
            CreateNoWindow = true,
            WindowStyle = ProcessWindowStyle.Hidden
        };
        startInfo.EnvironmentVariables["PYTHONUTF8"] = "1";
        startInfo.EnvironmentVariables["PYTHONUNBUFFERED"] = "1";
        startInfo.EnvironmentVariables["BACKEND_API_URL"] = "http://127.0.0.1:8001";
        startInfo.EnvironmentVariables["NODE_ENV"] = "development";
        // Explorer's PATH can predate a Node installation. npm.cmd needs its sibling node.exe.
        startInfo.EnvironmentVariables["PATH"] = Path.GetDirectoryName(executable) + ";" +
            (Environment.GetEnvironmentVariable("PATH") ?? string.Empty);

        Process process = Process.Start(startInfo);
        if (process == null)
        {
            throw new InvalidOperationException("无法启动命令：" + executable);
        }
    }

    private static string JoinArguments(string prefix, string argument)
    {
        return string.IsNullOrWhiteSpace(prefix) ? argument : prefix + " " + argument;
    }

    private static bool HasArgument(string[] args, string expected)
    {
        foreach (string arg in args)
        {
            if (string.Equals(arg, expected, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }
        return false;
    }

    private static void ShowError(string message)
    {
        Environment.ExitCode = 1;
        if (launcherLog != null) File.AppendAllText(launcherLog, message + Environment.NewLine, Encoding.UTF8);
        if (!quiet) MessageBox.Show(message, "Weibull 调试启动器", MessageBoxButtons.OK, MessageBoxIcon.Error);
    }

    private sealed class ToolCommand
    {
        public ToolCommand(string executable, string argumentPrefix)
        {
            Executable = executable;
            ArgumentPrefix = argumentPrefix;
        }

        public string Executable { get; private set; }
        public string ArgumentPrefix { get; private set; }
    }
}
