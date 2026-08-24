using UnityEngine;

public class TitleStart : MonoBehaviour
{
    [SerializeField] private DoorController doorController;

    public void StartLoadingLINE()
    {
        if (doorController == null)
        {
            Debug.LogError("DoorControllerが設定されていません。");
            return;
        }

        doorController.StartEntranceAnimation();
    }
}