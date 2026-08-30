#if UNITY_EDITOR
using System;
using System.Diagnostics;
using System.IO;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;

public class MagicPhotoBuildProcessor :
    IPreprocessBuildWithReport,
    IPostprocessBuildWithReport
{
    public int callbackOrder => 0;

    public void OnPreprocessBuild(BuildReport report)
    {
        if (report.summary.platform != BuildTarget.StandaloneWindows &&
            report.summary.platform != BuildTarget.StandaloneWindows64)
        {
            throw new BuildFailedException(
                "MagicPhotoの提出用ビルドはWindows向けにしてください。"
            );
        }

        string projectRoot = GetProjectRoot();
        string pythonDirectory = Path.Combine(projectRoot, "Python");
        string analyzerPath = Path.Combine(
            pythonDirectory,
            "dist",
            "demo_click_udp",
            "demo_click_udp.exe"
        );

        if (NeedsAnalyzerBuild(pythonDirectory, analyzerPath))
        {
            BuildAnalyzer(projectRoot);
        }

        if (!File.Exists(analyzerPath))
        {
            throw new BuildFailedException(
                "Python解析exeを作成できませんでした: " +
                analyzerPath
            );
        }
    }

    public void OnPostprocessBuild(
        BuildReport report
    )
    {
        string projectRoot = GetProjectRoot();
        string buildRoot = Path.GetDirectoryName(
            report.summary.outputPath
        );

        if (string.IsNullOrWhiteSpace(buildRoot))
        {
            throw new BuildFailedException(
                "ビルド先フォルダを取得できませんでした。"
            );
        }

        CopyDirectory(
            Path.Combine(projectRoot, "Python", "dist"),
            Path.Combine(buildRoot, "Python", "dist")
        );

        CopyDirectory(
            Path.Combine(projectRoot, "PhotoLibrary"),
            Path.Combine(buildRoot, "PhotoLibrary")
        );

        Directory.CreateDirectory(
            Path.Combine(buildRoot, "Python", "objects")
        );
        Directory.CreateDirectory(
            Path.Combine(buildRoot, "downloaded_images")
        );

        UnityEngine.Debug.Log(
            "MagicPhoto実行ファイルと写真素材をビルド先へ配置しました: " +
            buildRoot
        );
    }

    private static bool NeedsAnalyzerBuild(
        string pythonDirectory,
        string analyzerPath
    )
    {
        if (!File.Exists(analyzerPath))
        {
            return true;
        }

        DateTime executableTime =
            File.GetLastWriteTimeUtc(analyzerPath);

        foreach (string sourcePath in Directory.GetFiles(
            pythonDirectory,
            "*.py",
            SearchOption.TopDirectoryOnly
        ))
        {
            if (File.GetLastWriteTimeUtc(sourcePath) > executableTime)
            {
                return true;
            }
        }

        string specPath = Path.Combine(
            pythonDirectory,
            "demo_click_udp.spec"
        );

        return File.Exists(specPath) &&
            File.GetLastWriteTimeUtc(specPath) > executableTime;
    }

    private static void BuildAnalyzer(string projectRoot)
    {
        string buildScript = Path.Combine(
            projectRoot,
            "Python",
            "Build-DemoExecutable.ps1"
        );

        ProcessStartInfo startInfo = new ProcessStartInfo
        {
            FileName = "powershell.exe",
            Arguments =
                "-NoProfile -ExecutionPolicy Bypass -File \"" +
                buildScript +
                "\"",
            WorkingDirectory = Path.Combine(projectRoot, "Python"),
            UseShellExecute = false,
            CreateNoWindow = true
        };

        using (Process process = Process.Start(startInfo))
        {
            if (process == null)
            {
                throw new BuildFailedException(
                    "Python解析exeの作成処理を開始できませんでした。"
                );
            }

            process.WaitForExit();

            if (process.ExitCode != 0)
            {
                throw new BuildFailedException(
                    "Python解析exeの作成に失敗しました。" +
                    "Python/Build-DemoExecutable.ps1を確認してください。"
                );
            }
        }
    }

    private static string GetProjectRoot()
    {
        return Path.GetFullPath(
            Path.Combine(Application.dataPath, "..")
        );
    }

    private static void CopyDirectory(
        string sourceDirectory,
        string destinationDirectory
    )
    {
        string sourcePath = Path.GetFullPath(sourceDirectory);
        string destinationPath =
            Path.GetFullPath(destinationDirectory);

        if (string.Equals(
            sourcePath.TrimEnd(Path.DirectorySeparatorChar),
            destinationPath.TrimEnd(Path.DirectorySeparatorChar),
            StringComparison.OrdinalIgnoreCase
        ))
        {
            return;
        }

        if (!Directory.Exists(sourcePath))
        {
            throw new BuildFailedException(
                "コピー元フォルダが見つかりません: " +
                sourcePath
            );
        }

        if (Directory.Exists(destinationPath))
        {
            Directory.Delete(destinationPath, true);
        }

        Directory.CreateDirectory(destinationPath);

        foreach (string sourceFile in Directory.GetFiles(
            sourcePath,
            "*",
            SearchOption.AllDirectories
        ))
        {
            string relativePath = sourceFile.Substring(
                sourcePath.Length
            ).TrimStart(
                Path.DirectorySeparatorChar,
                Path.AltDirectorySeparatorChar
            );

            string destinationFile = Path.Combine(
                destinationPath,
                relativePath
            );

            Directory.CreateDirectory(
                Path.GetDirectoryName(destinationFile)
            );
            File.Copy(sourceFile, destinationFile, true);
        }
    }
}
#endif
