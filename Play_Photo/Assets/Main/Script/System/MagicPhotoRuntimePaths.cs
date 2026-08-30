using System.IO;
using UnityEngine;

public static class MagicPhotoRuntimePaths
{
    public static string RootDirectory
    {
        get
        {
#if UNITY_EDITOR
            return Path.GetFullPath(
                Path.Combine(Application.dataPath, "..")
            );
#else
            DirectoryInfo dataDirectory =
                Directory.GetParent(Application.dataPath);

            return dataDirectory != null
                ? dataDirectory.FullName
                : Path.GetFullPath(
                    Path.Combine(Application.dataPath, "..")
                );
#endif
        }
    }

    public static string PythonDirectory =>
        Path.Combine(RootDirectory, "Python");

    public static string DownloadedImagesDirectory =>
        Path.Combine(RootDirectory, "downloaded_images");

    public static string CutoutDirectory =>
        Path.Combine(PythonDirectory, "objects");

    public static string ProgressFilePath =>
        Path.Combine(PythonDirectory, "loading_progress.txt");

    public static string AnalysisResultPath =>
        Path.Combine(PythonDirectory, "analysis_result.json");

    public static string PhotoLibraryDirectory =>
        Path.Combine(RootDirectory, "PhotoLibrary");

    public static string PackagedAnalyzerDirectory =>
        Path.Combine(PythonDirectory, "dist", "demo_click_udp");

    public static string PackagedAnalyzerPath =>
        Path.Combine(
            PackagedAnalyzerDirectory,
            "demo_click_udp.exe"
        );

    public static void EnsureWorkingDirectories()
    {
        Directory.CreateDirectory(DownloadedImagesDirectory);
        Directory.CreateDirectory(CutoutDirectory);
    }
}
