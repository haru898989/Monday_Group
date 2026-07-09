using UnityEngine;
using System.Collections;
using System.Diagnostics;
using System.IO;

public class ServerStarter : MonoBehaviour
{
    void Start()
    {
        StartCoroutine(StartLineServerAndNgrok());
    }

    IEnumerator StartLineServerAndNgrok()
    {
        string projectPath = Directory.GetCurrentDirectory();

        string lineServerPath = Path.Combine(projectPath, "Python", "dist", "Line_Server.exe");

        if (File.Exists(lineServerPath))
        {
            Process.Start(lineServerPath);
            UnityEngine.Debug.Log("Line_Server.exe を起動しました");
        }
        else
        {
            UnityEngine.Debug.LogError("Line_Server.exe が見つかりません: " + lineServerPath);
        }

        yield return new WaitForSeconds(3f);

        ProcessStartInfo ngrokInfo = new ProcessStartInfo();
        ngrokInfo.FileName = "cmd.exe";
        ngrokInfo.Arguments = "/c ngrok http --url=unwritten-revolver-vexingly.ngrok-free.dev 5000";
        ngrokInfo.UseShellExecute = true;
        ngrokInfo.CreateNoWindow = false;

        Process.Start(ngrokInfo);
        UnityEngine.Debug.Log("ngrok を起動しました");
    }
}