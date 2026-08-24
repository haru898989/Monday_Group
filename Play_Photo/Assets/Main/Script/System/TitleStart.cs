using System.Collections;
using UnityEngine;

public class TitleStart : MonoBehaviour
{
    [SerializeField] private DoorController doorController;

    [Header("スタート時に消すUI")]
    [SerializeField] private GameObject titleImage;
    [SerializeField] private GameObject startButton;

    [Header("フェードアウト設定")]
    [SerializeField] private float fadeOutDuration = 0.5f;

    private bool isStarting = false;

    public void StartLoadingLINE()
    {
        // 連打防止
        if (isStarting)
        {
            return;
        }

        if (doorController == null)
        {
            Debug.LogError("DoorControllerが設定されていません。");
            return;
        }

        isStarting = true;

        StartCoroutine(StartSequence());
    }

    private IEnumerator StartSequence()
    {
        // ボタンを押せなくする
        if (startButton != null)
        {
            ButtonInteraction(false);
        }

        // ドアを開き始める
        doorController.StartEntranceAnimation();

        // タイトルとスタートボタンを徐々に消す
        CanvasGroup titleGroup = null;
        CanvasGroup buttonGroup = null;

        if (titleImage != null)
        {
            titleGroup = titleImage.GetComponent<CanvasGroup>();
        }

        if (startButton != null)
        {
            buttonGroup = startButton.GetComponent<CanvasGroup>();
        }

        float titleStartAlpha =
            titleGroup != null ? titleGroup.alpha : 1f;

        float buttonStartAlpha =
            buttonGroup != null ? buttonGroup.alpha : 1f;

        float elapsedTime = 0f;

        while (elapsedTime < fadeOutDuration)
        {
            elapsedTime += Time.deltaTime;

            float t = Mathf.Clamp01(
                elapsedTime / fadeOutDuration
            );

            t = Mathf.SmoothStep(0f, 1f, t);

            if (titleGroup != null)
            {
                titleGroup.alpha =
                    Mathf.Lerp(titleStartAlpha, 0f, t);
            }

            if (buttonGroup != null)
            {
                buttonGroup.alpha =
                    Mathf.Lerp(buttonStartAlpha, 0f, t);
            }

            yield return null;
        }

        if (titleGroup != null)
        {
            titleGroup.alpha = 0f;
        }

        if (buttonGroup != null)
        {
            buttonGroup.alpha = 0f;
        }
    }

    private void ButtonInteraction(bool enabled)
    {
        CanvasGroup buttonGroup =
            startButton.GetComponent<CanvasGroup>();

        if (buttonGroup != null)
        {
            buttonGroup.interactable = enabled;
            buttonGroup.blocksRaycasts = enabled;
        }
    }
}