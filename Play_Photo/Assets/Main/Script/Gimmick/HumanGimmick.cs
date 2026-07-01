using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class HumanGimmick : MonoBehaviour, GimmickBase
{
    [SerializeField]
    private AudioSource audioSource;

    public void ActivateMagic()
    {
        Debug.Log("ギミック発動");

        SoundManager.Instance.PlaySE(0);
    }

}
