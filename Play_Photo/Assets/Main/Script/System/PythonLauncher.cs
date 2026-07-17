using System;
using System.Diagnostics;
using System.IO;
using UnityEngine;

public class PythonLauncher : MonoBehaviour
{
    private Process pythonProcess;

    void Start()
    {
        StartPython();
    }

    private void StartPython()
    {
        try
        {
            // Play_Photo/Python フォルダの場所を作る
            string pythonFolder = Path.GetFullPath(
                Path.Combine(Application.dataPath, "..", "Python")
            );

            // 起動するPythonファイル
            string pythonFilePath = Path.Combine(
                pythonFolder,
                "demo_click.py"
            );

            if (!File.Exists(pythonFilePath))
            {
                UnityEngine.Debug.LogError(
                    $"demo_click.pyが見つかりません: {pythonFilePath}"
                );
                return;
            }

            ProcessStartInfo startInfo = new ProcessStartInfo
            {
                FileName = "python",
                Arguments = $"\"{pythonFilePath}\"",
                WorkingDirectory = pythonFolder,
                UseShellExecute = false,
                CreateNoWindow = false
            };

            pythonProcess = Process.Start(startInfo);

            UnityEngine.Debug.Log(
                $"Pythonを起動しました: {pythonFilePath}"
            );
        }
        catch (Exception error)
        {
            UnityEngine.Debug.LogError(
                $"Python起動エラー: {error.Message}"
            );
        }
    }

    private void StopPython()
    {
        try
        {
            if (pythonProcess != null && !pythonProcess.HasExited)
            {
                pythonProcess.Kill();
                pythonProcess.WaitForExit();
            }
        }
        catch (Exception error)
        {
            UnityEngine.Debug.LogWarning(
                $"Python終了時の警告: {error.Message}"
            );
        }
        finally
        {
            pythonProcess?.Dispose();
            pythonProcess = null;
        }
    }

    void OnDestroy()
    {
        StopPython();
    }

    void OnApplicationQuit()
    {
        StopPython();
    }
}
