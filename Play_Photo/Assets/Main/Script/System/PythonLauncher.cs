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
            // Play_Photo/Python �t�H���_�̏ꏊ�����
            string pythonFolder = Path.GetFullPath(
                Path.Combine(Application.dataPath, "..", "Python")
            );

            // �N������Python�t�@�C��
            string pythonFilePath = Path.Combine(
                pythonFolder,
                "demo_click_udp.py"
            );

            if (!File.Exists(pythonFilePath))
            {
                UnityEngine.Debug.LogError(
                    $"demo_click.py��������܂���: {pythonFilePath}"
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
                $"Python���N�����܂���: {pythonFilePath}"
            );
        }
        catch (Exception error)
        {
            UnityEngine.Debug.LogError(
                $"Python�N���G���[: {error.Message}"
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
                $"Python�I�����̌x��: {error.Message}"
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
