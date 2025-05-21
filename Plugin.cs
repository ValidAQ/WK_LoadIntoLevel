using BepInEx;
using BepInEx.Logging;
using BepInEx.Configuration;
using UnityEngine.SceneManagement;

namespace WK_LoadIntoPlayground;


[BepInPlugin(pluginGuid, pluginName, pluginVersion)]
public class LoadIntoPlayground : BaseUnityPlugin
{
    private const string pluginGuid = "com.validaq.loadintoplayground";
    private const string pluginName = "WK_LoadIntoPlayground";
    public const string pluginVersion = "0.0.1";

    private ConfigEntry<string> sceneToReplace;
    internal static new ManualLogSource Logger;

    private void Awake()
    {
        Logger = base.Logger;

        sceneToReplace = Config.Bind(
            "General",      // The section under which the option is shown
            "PlaygroundScene",  // The key of the configuration option in the configuration file
            "Intro", // The default value
            "Game scene to be replaced with the Playground scene. " +
            "Use 'Intro' to instantly load into the playground upon game launch, " +
            "or 'Training-Level' to load into the Playground when starting the tutorial. " +
            "It's advised to avoid using 'Main-Menu', as it will make you "+
            "unable to return to main menu from the playground, leaving Alt-F4 as the only way to exit."
            // Description of the option to show in the config file
        );

        SceneManager.sceneLoaded += OnSceneLoad;

        Logger.LogInfo($"Plugin {pluginGuid} is loaded!");
    }

    private void OnSceneLoad(Scene scene, LoadSceneMode mode)
    {
        bool menuLoaded = scene.name == sceneToReplace.Value;
        if (menuLoaded)
        {
            SceneManager.LoadScene("Playground");
        }
    }
}
