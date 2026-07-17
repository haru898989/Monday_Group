using UnityEngine;
using UnityEngine.SceneManagement;
using System.Collections;
using System.Diagnostics;
using System.IO;

public class ServerStarter : MonoBehaviour
{
    private string imageFolderPath;

    private bool imageDetected;
    private bool imageSaveCompleted;
    private bool processesStopped;

    // 起動したプロセスを記録する
    private Process lineServerProcess;
    private Process ngrokProcess;

    private void Start()
    {
        StartCoroutine(StartLineServerAndNgrok());
    }

    /// <summary>
    /// LINEサーバーとngrokを起動し、
    /// downloaded_imagesの監視を開始する
    /// </summary>
    private IEnumerator StartLineServerAndNgrok()
    {
        // Unityプロジェクトのフォルダー
        string projectPath = Directory.GetCurrentDirectory();

        // Play_Photo/downloaded_images
        imageFolderPath = Path.Combine(
            projectPath,
            "downloaded_images"
        );

        // 前回利用した人の画像を削除する
        DeleteOldImages(imageFolderPath);

        // Python/dist/Line_Server.exe
        string lineServerPath = Path.Combine(
            projectPath,
            "Python",
            "dist",
            "Line_Server.exe"
        );

        if (File.Exists(lineServerPath))
        {
            try
            {
                lineServerProcess =
                    Process.Start(lineServerPath);

                UnityEngine.Debug.Log(
                    "Line_Server.exe を起動しました"
                );
            }
            catch (System.Exception exception)
            {
                UnityEngine.Debug.LogError(
                    "Line_Server.exeを起動できませんでした: "
                    + exception.Message
                );

                yield break;
            }
        }
        else
        {
            UnityEngine.Debug.LogError(
                "Line_Server.exeが見つかりません: "
                + lineServerPath
            );

            yield break;
        }

        // 現在使用している待ち時間
        yield return new WaitForSeconds(3f);

        // ngrokを起動する
        ProcessStartInfo ngrokInfo =
            new ProcessStartInfo();

        ngrokInfo.FileName = "cmd.exe";

        ngrokInfo.Arguments =
            "/c ngrok http --url=unwritten-revolver-vexingly.ngrok-free.dev 5000";

        ngrokInfo.UseShellExecute = true;
        ngrokInfo.CreateNoWindow = false;

        try
        {
            ngrokProcess =
                Process.Start(ngrokInfo);

            UnityEngine.Debug.Log(
                "ngrokを起動しました"
            );
        }
        catch (System.Exception exception)
        {
            UnityEngine.Debug.LogError(
                "ngrokを起動できませんでした: "
                + exception.Message
            );

            StopBackgroundProcesses();

            yield break;
        }

        // 画像フォルダーの監視を開始する
        StartCoroutine(MonitorImageFolder());
    }

    /// <summary>
    /// downloaded_images内に画像が保存されたか監視する
    /// </summary>
    private IEnumerator MonitorImageFolder()
    {
        imageDetected = false;

        UnityEngine.Debug.Log(
            "画像フォルダーの監視を開始しました: "
            + imageFolderPath
        );

        while (!imageDetected)
        {
            if (Directory.Exists(imageFolderPath))
            {
                string[] files =
                    Directory.GetFiles(imageFolderPath);

                foreach (string filePath in files)
                {
                    if (!IsImageFile(filePath))
                    {
                        continue;
                    }

                    imageDetected = true;

                    UnityEngine.Debug.Log(
                        "新しい画像を検知しました: "
                        + filePath
                    );

                    // 画像の保存完了を待つ
                    yield return StartCoroutine(
                        WaitForImageSaveCompletion(filePath)
                    );

                    if (imageSaveCompleted)
                    {
                        // サーバーとngrokを停止する
                        StopBackgroundProcesses();

                        // Main Sceneへ移動する
                        LoadMainScene();

                        yield break;
                    }

                    imageDetected = false;

                    UnityEngine.Debug.LogWarning(
                        "画像の保存完了を確認できなかったため、"
                        + "フォルダー監視を再開します"
                    );

                    break;
                }
            }

            yield return new WaitForSeconds(0.5f);
        }
    }

    /// <summary>
    /// 対象ファイルが画像か確認する
    /// </summary>
    private bool IsImageFile(string filePath)
    {
        string extension =
            Path.GetExtension(filePath).ToLower();

        return extension == ".jpg"
            || extension == ".jpeg"
            || extension == ".png";
    }

    /// <summary>
    /// 画像ファイルの書き込みが完了するまで待つ
    /// </summary>
    private IEnumerator WaitForImageSaveCompletion(
        string filePath
    )
    {
        imageSaveCompleted = false;

        UnityEngine.Debug.Log(
            "画像の保存完了を確認しています"
        );

        long previousFileSize = -1;
        int stableCount = 0;

        float timeout = 10f;
        float elapsedTime = 0f;
        float checkInterval = 0.5f;

        while (elapsedTime < timeout)
        {
            bool fileCheckSucceeded = false;
            long currentFileSize = 0;

            if (File.Exists(filePath))
            {
                try
                {
                    FileInfo fileInfo =
                        new FileInfo(filePath);

                    currentFileSize =
                        fileInfo.Length;

                    fileCheckSucceeded = true;
                }
                catch (System.Exception exception)
                {
                    UnityEngine.Debug.LogWarning(
                        "画像ファイルを確認できませんでした: "
                        + exception.Message
                    );

                    fileCheckSucceeded = false;
                }
            }

            if (fileCheckSucceeded)
            {
                if (currentFileSize > 0
                    && currentFileSize == previousFileSize)
                {
                    stableCount++;
                }
                else
                {
                    stableCount = 0;
                }

                previousFileSize = currentFileSize;

                // 2回連続でサイズが変わらず、
                // ファイルを開ければ保存完了
                if (stableCount >= 2
                    && CanOpenFile(filePath))
                {
                    imageSaveCompleted = true;

                    UnityEngine.Debug.Log(
                        "画像の保存完了を確認しました: "
                        + filePath
                    );

                    yield break;
                }
            }
            else
            {
                stableCount = 0;
                previousFileSize = -1;
            }

            yield return new WaitForSeconds(
                checkInterval
            );

            elapsedTime += checkInterval;
        }

        UnityEngine.Debug.LogError(
            "画像の保存完了を確認できませんでした: "
            + filePath
        );
    }

    /// <summary>
    /// ファイルが書き込み中ではないか確認する
    /// </summary>
    private bool CanOpenFile(string filePath)
    {
        try
        {
            using (FileStream stream = new FileStream(
                filePath,
                FileMode.Open,
                FileAccess.Read,
                FileShare.None
            ))
            {
                return stream.Length > 0;
            }
        }
        catch (IOException)
        {
            return false;
        }
        catch (System.Exception exception)
        {
            UnityEngine.Debug.LogWarning(
                "画像ファイルの確認中に問題が発生しました: "
                + exception.Message
            );

            return false;
        }
    }

    /// <summary>
    /// Line_Server.exeとngrokを停止する
    /// </summary>
    private void StopBackgroundProcesses()
    {
        // 二重停止を防ぐ
        if (processesStopped)
        {
            return;
        }

        processesStopped = true;

        UnityEngine.Debug.Log(
            "Line_Server.exeとngrokを停止します"
        );

        StopProcessTree(
            ngrokProcess,
            "ngrok"
        );

        StopProcessTree(
            lineServerProcess,
            "Line_Server.exe"
        );

        UnityEngine.Debug.Log(
            "バックグラウンド処理の停止が完了しました"
        );
    }

    /// <summary>
    /// 指定したプロセスと子プロセスを停止する
    /// </summary>
    private void StopProcessTree(
        Process process,
        string processName
    )
    {
        if (process == null)
        {
            UnityEngine.Debug.LogWarning(
                processName
                + "のプロセス情報がありません"
            );

            return;
        }

        try
        {
            process.Refresh();

            if (process.HasExited)
            {
                UnityEngine.Debug.Log(
                    processName
                    + "はすでに終了しています"
                );

                return;
            }

            int processId = process.Id;

            // Windowsのtaskkillを使用して、
            // 子プロセスもまとめて停止する
            ProcessStartInfo taskKillInfo =
                new ProcessStartInfo();

            taskKillInfo.FileName = "taskkill";

            taskKillInfo.Arguments =
                "/PID "
                + processId
                + " /T /F";

            taskKillInfo.UseShellExecute = false;
            taskKillInfo.CreateNoWindow = true;

            using (Process taskKillProcess =
                Process.Start(taskKillInfo))
            {
                if (taskKillProcess != null)
                {
                    taskKillProcess.WaitForExit(
                        3000
                    );
                }
            }

            UnityEngine.Debug.Log(
                processName
                + "を停止しました"
            );
        }
        catch (System.Exception exception)
        {
            UnityEngine.Debug.LogWarning(
                processName
                + "を停止できませんでした: "
                + exception.Message
            );
        }
        finally
        {
            process.Dispose();
        }
    }

    /// <summary>
    /// Main Sceneへ移動する
    /// </summary>
    private void LoadMainScene()
    {
        UnityEngine.Debug.Log(
            "Main Sceneへ移動します"
        );

        SceneManager.LoadScene("Main");
    }

    /// <summary>
    /// downloaded_images内に残っている
    /// 前回の画像を削除する
    /// </summary>
    private void DeleteOldImages(string folderPath)
    {
        try
        {
            if (!Directory.Exists(folderPath))
            {
                Directory.CreateDirectory(folderPath);

                UnityEngine.Debug.Log(
                    "downloaded_imagesフォルダーを作成しました: "
                    + folderPath
                );

                return;
            }

            string[] files =
                Directory.GetFiles(folderPath);

            foreach (string filePath in files)
            {
                File.Delete(filePath);

                UnityEngine.Debug.Log(
                    "前回の画像を削除しました: "
                    + filePath
                );
            }

            UnityEngine.Debug.Log(
                "downloaded_imagesの初期化が完了しました"
            );
        }
        catch (System.Exception exception)
        {
            UnityEngine.Debug.LogError(
                "前回の画像を削除できませんでした: "
                + exception.Message
            );
        }
    }

    /// <summary>
    /// Unityの再生を途中で終了した場合にも停止する
    /// </summary>
    private void OnApplicationQuit()
    {
        StopBackgroundProcesses();
    }

    /// <summary>
    /// ServerStarterが削除された場合にも停止する
    /// </summary>
    private void OnDestroy()
    {
        StopBackgroundProcesses();
    }
}