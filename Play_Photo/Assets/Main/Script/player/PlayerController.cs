using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;

public class PlayerController : MonoBehaviour
{
    private PlayerInput playerInput_;

    void Start()
    {
        playerInput_ = new PlayerInput();
        playerInput_.Enable();
    }

    void Update()
    {
        if (playerInput_.Player.touch.triggered)
        {
            Vector2 screenPosition = Pointer.current.position.ReadValue();
            Ray ray = Camera.main.ScreenPointToRay(screenPosition);
            RaycastHit hit;

            if(Physics.Raycast(ray, out hit))
            {
                GimmickBase touchGimmick = hit.collider.GetComponent<GimmickBase>();
                if(touchGimmick != null)
                {
                    touchGimmick.ActivateMagic();
                }
            }
        }
    }
}
