using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Windows.Forms;

[assembly: AssemblyTitle("Weibull 本地启动器")]
[assembly: AssemblyDescription("启动本地 Weibull 前后端并打开默认浏览器")]
[assembly: AssemblyCompany("weibull.work")]
[assembly: AssemblyProduct("Weibull Local Launcher")]
[assembly: AssemblyVersion("1.0.0.0")]

internal static class WeibullLocalLauncher
{
    private const string FrontendUrl = "http://localhost:3000";
    private const string BackendProbeUrl = "http://127.0.0.1:8001/openapi.json";
    private const int StartupTimeoutSeconds = 120;

    [STAThread]
    private static void Main(string[] args)
    {
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

                bool backendReady = IsBackendReady();
                bool frontendReady = IsFrontendReady();

                if (!backendReady)
                {
                    ToolCommand python = ResolvePython(projectRoot);
                    if (python == null)
                    {
                        ShowError("没有找到可用的 Python。请安装 Python，或在项目中创建 .venv/venv 虚拟环境。\n\n项目目录：" + projectRoot);
                        return;
                    }

                    StartHiddenCommand(
                        python.Executable,
                        JoinArguments(python.ArgumentPrefix, "main.py"),
                        Path.Combine(projectRoot, "python"),
                        Path.Combine(logDirectory, "local-launcher-backend.log"));
                }

                if (!frontendReady)
                {
                    string npm = ResolveNpm();
                    if (npm == null)
                    {
                        ShowError("没有找到 npm.cmd。请先安装 Node.js，并确认 npm 已加入 PATH。\n\n项目目录：" + projectRoot);
                        return;
                    }

                    StartHiddenCommand(
                        npm,
                        "run dev",
                        projectRoot,
                        Path.Combine(logDirectory, "local-launcher-frontend.log"));
                }

                DateTime deadline = DateTime.UtcNow.AddSeconds(StartupTimeoutSeconds);
                while (DateTime.UtcNow < deadline)
                {
                    backendReady = backendReady || IsBackendReady();
                    frontendReady = frontendReady || IsFrontendReady();
                    if (backendReady && frontendReady)
                    {
                        if (!HasArgument(args, "--no-browser"))
                        {
                            Process.Start(new ProcessStartInfo(FrontendUrl) { UseShellExecute = true });
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
                    "本地环境在 120 秒内未完全启动：\n" + missing +
                    "\n请查看日志目录：\n" + logDirectory);
            }
            catch (Exception exception)
            {
                ShowError("启动失败：\n" + exception.Message);
            }
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
            Path.Combine(projectRoot, ".venv", "Scripts", "python.exe"),
            Path.Combine(projectRoot, "venv", "Scripts", "python.exe"),
            Path.Combine(projectRoot, "python", ".venv", "Scripts", "python.exe"),
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
        MessageBox.Show(message, "Weibull 本地启动器", MessageBoxButtons.OK, MessageBoxIcon.Error);
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
