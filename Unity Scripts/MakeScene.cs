using UnityEngine;
using UnityEditor.PackageManager;
using UnityEngine.SceneManagement;
using UnityEditor.SceneManagement;
using UnityEditor.PackageManager.Requests;

public class MakeScene : MonoBehaviour
{
	static string projectPath;

	[MenuItem("Tools/Make scene")]
	public static void Do ()
	{
		AddPackage ("com.unity.vectorgraphics");
		Scene scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene);
		EditorSceneManager.SaveScene(scene, "Assets/Scenes/Test.unity");
		EditorSceneManager.OpenScene(scene.path);
		string[] svgsPaths = GetAllFilePathsInFolder("Assets/Art/Svgs", ".svg");
		foreach (string svgPath in svgsPaths)
		{
			Object[] obs = AssetDatabase.LoadAllAssetsAtPath(svgPath);
			foreach (Object ob in obs)
			{
				print(ob);
			}
		}
	}

	static void AddPackage (string name)
	{
		AddRequest addRequest = Client.Add(name);
		while (!addRequest.IsCompleted)
		{
		}
		if (addRequest.Error == null)
			print("Package " + name + " added");
		else
			print(addRequest.Error);
	}
}