using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using UnityEngine;

public class PythonLauncher : MonoBehaviour
{
    [SerializeField]
    private string pythonExecutablePath = "";

    [SerializeField]
    private string pythonScriptName = "demo_click_udp.py";

    [SerializeField]
    private float startupCheckSeconds = 1.5f;

    private Process pythonProcess;


    private class PythonCommand
    {
        public string executable;
        public string argumentPrefix;

        public PythonCommand(
            string executablePath,
            string prefix = ""
        )
        {
            executable = executablePath;
            argumentPrefix = prefix;
        }
    }


    private void Start()
    {
        StartCoroutine(StartPython());
    }


    private IEnumerator StartPython()
    {
        MagicPhotoRuntimePaths.EnsureWorkingDirectories();

        bool usePackagedExecutable = !Application.isEditor;

        string pythonFolder = usePackagedExecutable
            ? MagicPhotoRuntimePaths.PackagedAnalyzerDirectory
            : MagicPhotoRuntimePaths.PythonDirectory;

        string pythonFilePath = usePackagedExecutable
            ? MagicPhotoRuntimePaths.PackagedAnalyzerPath
            : Path.Combine(pythonFolder, pythonScriptName);

        if (!File.Exists(pythonFilePath))
        {
            UnityEngine.Debug.LogError(
                "Pythonスクリプトが見つかりません: "
                + pythonFilePath
            );
            yield break;
        }

        List<string> errors = new List<string>();

        List<PythonCommand> commands = usePackagedExecutable
            ? new List<PythonCommand>
            {
                new PythonCommand(pythonFilePath)
            }
            : BuildPythonCandidates(pythonFolder);

        foreach (
            PythonCommand command
            in commands
        )
        {
            Process candidateProcess = null;
            StringBuilder processError = new StringBuilder();

            try
            {
                string arguments = usePackagedExecutable
                    ? string.Empty
                    : string.IsNullOrWhiteSpace(
                        command.argumentPrefix
                    )
                        ? $"\"{pythonFilePath}\""
                        : command.argumentPrefix
                            + " \""
                            + pythonFilePath
                            + "\"";

                ProcessStartInfo startInfo =
                    new ProcessStartInfo
                    {
                        FileName = command.executable,
                        Arguments = arguments,
                        WorkingDirectory = pythonFolder,
                        UseShellExecute = false,
                        CreateNoWindow = true,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true
                    };

                startInfo.EnvironmentVariables[
                    "MAGIC_PHOTO_DATA_DIR"
                ] = MagicPhotoRuntimePaths.DownloadedImagesDirectory;
                startInfo.EnvironmentVariables[
                    "MAGIC_PHOTO_CUTOUT_DIR"
                ] = MagicPhotoRuntimePaths.CutoutDirectory;
                startInfo.EnvironmentVariables[
                    "MAGIC_PHOTO_PROGRESS_FILE"
                ] = MagicPhotoRuntimePaths.ProgressFilePath;
                startInfo.EnvironmentVariables[
                    "MAGIC_PHOTO_ANALYSIS_RESULT"
                ] = MagicPhotoRuntimePaths.AnalysisResultPath;

                candidateProcess = new Process
                {
                    StartInfo = startInfo,
                    EnableRaisingEvents = true
                };

                candidateProcess.ErrorDataReceived +=
                    (sender, eventArgs) =>
                    {
                        if (!string.IsNullOrWhiteSpace(
                                eventArgs.Data
                            ))
                        {
                            lock (processError)
                            {
                                processError.AppendLine(
                                    eventArgs.Data
                                );
                            }
                        }
                    };

                if (!candidateProcess.Start())
                {
                    throw new InvalidOperationException(
                        "プロセスを開始できませんでした。"
                    );
                }

                candidateProcess.BeginOutputReadLine();
                candidateProcess.BeginErrorReadLine();
                pythonProcess = candidateProcess;
            }
            catch (Exception error)
            {
                errors.Add(
                    command.executable
                    + ": "
                    + error.Message
                );

                candidateProcess?.Dispose();
                candidateProcess = null;
                pythonProcess = null;
                continue;
            }

            float elapsedTime = 0f;
            float checkTime =
                Mathf.Max(startupCheckSeconds, 0.2f);

            while (
                elapsedTime < checkTime &&
                !candidateProcess.HasExited
            )
            {
                elapsedTime += Time.unscaledDeltaTime;
                yield return null;
            }

            if (candidateProcess.HasExited)
            {
                candidateProcess.WaitForExit();

                if (candidateProcess.ExitCode != 0)
                {
                    string errorText;
                    lock (processError)
                    {
                        errorText =
                            processError.ToString().Trim();
                    }

                    errors.Add(
                        command.executable
                        + ": 終了コード "
                        + candidateProcess.ExitCode
                        + (string.IsNullOrWhiteSpace(errorText)
                            ? ""
                            : " / " + errorText)
                    );

                    candidateProcess.Dispose();
                    pythonProcess = null;
                    continue;
                }

                UnityEngine.Debug.Log(
                    "Python解析が完了しました: "
                    + command.executable
                );

                candidateProcess.Dispose();
                pythonProcess = null;
                yield break;
            }

            UnityEngine.Debug.Log(
                "Pythonを起動しました: "
                + command.executable
                + " "
                + pythonFilePath
            );
            yield break;
        }

        UnityEngine.Debug.LogError(
            "Pythonを起動できませんでした。"
            + " InspectorのPython Executable Path、"
            + "MAGIC_PHOTO_PYTHON環境変数、"
            + "またはプロジェクトの.venvを確認してください。\n"
            + string.Join("\n", errors)
        );
    }


    private List<PythonCommand> BuildPythonCandidates(
        string pythonFolder
    )
    {
        List<PythonCommand> candidates =
            new List<PythonCommand>();

        HashSet<string> registered =
            new HashSet<string>(
                StringComparer.OrdinalIgnoreCase
            );

        AddPythonCandidate(
            candidates,
            registered,
            pythonExecutablePath
        );

        AddPythonCandidate(
            candidates,
            registered,
            Environment.GetEnvironmentVariable(
                "MAGIC_PHOTO_PYTHON"
            )
        );

        string virtualEnvironment =
            Environment.GetEnvironmentVariable(
                "VIRTUAL_ENV"
            );

        if (!string.IsNullOrWhiteSpace(virtualEnvironment))
        {
            AddPythonCandidate(
                candidates,
                registered,
                Path.Combine(
                    virtualEnvironment,
                    "Scripts",
                    "python.exe"
                )
            );
        }

        string projectFolder = Path.GetFullPath(
            Path.Combine(pythonFolder, "..")
        );

        AddPythonCandidate(
            candidates,
            registered,
            Path.Combine(
                projectFolder,
                ".venv",
                "Scripts",
                "python.exe"
            )
        );

        AddPythonCandidate(
            candidates,
            registered,
            Path.Combine(
                pythonFolder,
                ".venv",
                "Scripts",
                "python.exe"
            )
        );

        AddPythonCandidate(
            candidates,
            registered,
            Path.Combine(
                projectFolder,
                "venv",
                "Scripts",
                "python.exe"
            )
        );

        AddInstalledPythonCandidates(
            candidates,
            registered
        );

        AddPythonCandidate(
            candidates,
            registered,
            "py",
            "-3"
        );

        AddPythonCandidate(
            candidates,
            registered,
            "python"
        );

        AddPythonCandidate(
            candidates,
            registered,
            "python3"
        );

        return candidates;
    }


    private void AddInstalledPythonCandidates(
        List<PythonCommand> candidates,
        HashSet<string> registered
    )
    {
        string localApplicationData =
            Environment.GetFolderPath(
                Environment.SpecialFolder.LocalApplicationData
            );

        if (string.IsNullOrWhiteSpace(localApplicationData))
        {
            return;
        }

        string pythonProgramsFolder = Path.Combine(
            localApplicationData,
            "Programs",
            "Python"
        );

        if (!Directory.Exists(pythonProgramsFolder))
        {
            return;
        }

        try
        {
            string[] installFolders =
                Directory.GetDirectories(
                    pythonProgramsFolder,
                    "Python*"
                );

            Array.Sort(
                installFolders,
                StringComparer.OrdinalIgnoreCase
            );
            Array.Reverse(installFolders);

            foreach (string installFolder in installFolders)
            {
                AddPythonCandidate(
                    candidates,
                    registered,
                    Path.Combine(
                        installFolder,
                        "python.exe"
                    )
                );
            }
        }
        catch (Exception error)
        {
            UnityEngine.Debug.LogWarning(
                "インストール済みPythonの検索に失敗しました: "
                + error.Message
            );
        }
    }


    private void AddPythonCandidate(
        List<PythonCommand> candidates,
        HashSet<string> registered,
        string executable,
        string argumentPrefix = ""
    )
    {
        if (string.IsNullOrWhiteSpace(executable))
        {
            return;
        }

        string normalizedExecutable =
            executable.Trim().Trim('"');

        string key =
            normalizedExecutable
            + "|"
            + argumentPrefix;

        if (!registered.Add(key))
        {
            return;
        }

        candidates.Add(
            new PythonCommand(
                normalizedExecutable,
                argumentPrefix
            )
        );
    }


    private void StopPython()
    {
        try
        {
            if (pythonProcess != null &&
                !pythonProcess.HasExited)
            {
                pythonProcess.Kill();
                pythonProcess.WaitForExit();
            }
        }
        catch (Exception error)
        {
            UnityEngine.Debug.LogWarning(
                "Python終了時の警告: "
                + error.Message
            );
        }
        finally
        {
            pythonProcess?.Dispose();
            pythonProcess = null;
        }
    }


    private void OnDestroy()
    {
        StopPython();
    }


    private void OnApplicationQuit()
    {
        StopPython();
    }
}
