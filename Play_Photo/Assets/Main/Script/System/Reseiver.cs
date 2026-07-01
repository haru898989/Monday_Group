using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System;
using static Reseiver;

public class Reseiver : MonoBehaviour
{
    private UdpClient client;
    private readonly int port = 1140;

    //Pythonから送られてくるJSONの形に合わせたクラスを定義
    [System.Serializable]
    public class ObjectData
    {
        public string name;
        public float x1;
        public float y1;

        public float x2;
        public float y2;

        public float x3;
        public float y3;

        public float x4;
        public float y4;
    }

    [System.Serializable]
    public class ReceivedData
    {
        public ObjectData[] objects;
    }

    // Start is called before the first frame update
    void Start()
    {
        client = new UdpClient(port);
        client.BeginReceive(ReceiveData, null);
    }

    // Update is called once per frame
    void Update()
    {
        
    }

    private void ReceiveData(IAsyncResult result)
    {
        try
        {
            //どこのデータでも受け取れる設定
            IPEndPoint ip = new IPEndPoint(IPAddress.Any, port);

            //届いたバイトデータを受け取る
            byte[] data = client.EndReceive(result, ref ip);

            //バイトデータを文字列(JSON)に変換
            string json = Encoding.UTF8.GetString(data);

        ReceivedData receivedData = JsonUtility.FromJson<ReceivedData>(json);

        foreach (ObjectData obj in receivedData.objects)
        {
            Debug.Log($"名前：{obj.name}");

            Debug.Log($"左上：({obj.x1},{obj.y1})");
            Debug.Log($"右上：({obj.x2},{obj.y2})");
            Debug.Log($"左下：({obj.x3},{obj.y3})");
            Debug.Log($"右下：({obj.x4},{obj.y4})");
        }
        

        }
        catch (Exception e)
        {
            Debug.LogError($"受信エラー: {e.Message}");
        }

        //次のデータを受け取るために、もう一度待機をスタートする
        if (client != null)
        {
            client.BeginReceive(ReceiveData, null);
        }
    }

    void OnDestroy()
    {
        //アプリ終了時やオブジェクトが消えるときに、必ずポートを閉じる
        if (client != null)
        {
            client.Close();
            client = null;
            Debug.Log("ポートを閉じました");
        }
        
    }
}
