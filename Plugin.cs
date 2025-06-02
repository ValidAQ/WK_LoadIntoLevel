using BepInEx;
using BepInEx.Logging;
using BepInEx.Configuration;
using UnityEngine.SceneManagement;

namespace LoadIntoLevel;


[BepInPlugin(MyPluginInfo.PLUGIN_GUID, MyPluginInfo.PLUGIN_NAME, MyPluginInfo.PLUGIN_VERSION)]
public class LoadIntoLevel : BaseUnityPlugin
{
    // BepInEx normally will use the AssemblyName from the project file as the plugin GUID.
    private const string pluginGuid = "com.validaq.loadintolevel";

    private ConfigEntry<string> sceneToReplace;
    private ConfigEntry<string> sceneToLoad;
    internal static new ManualLogSource Logger;

    private void Awake()
    {
        Logger = base.Logger;

        sceneToReplace = Config.Bind(
            "General",      // The section under which the option is shown
            "SceneToReplace",  // The key of the configuration option in the configuration file
            "Intro", // The default value
            "Game scene to be replaced. " +
            "Use 'Intro' to instantly load into the given scene upon game launch, " +
            "or 'Training-Level' to load into it when starting the tutorial. " +
            "It's advised to avoid using 'Main-Menu', as it will make you "+
            "unable to return to main menu from the scene, leaving Alt-F4 as the only way to exit."
            // Description of the option to show in the config file
        );

        sceneToLoad = Config.Bind(
            "General",
            "SceneToLoad",
            "Playground",
            "The name of the scene to load instead of the specified scene. " +
            "This should be the name of the scene you want to load into, such as 'Playground'."
        );

        SceneManager.sceneLoaded += OnSceneLoad;

        Logger.LogInfo($"Plugin {pluginGuid} is loaded!");
    }

    private void OnSceneLoad(Scene scene, LoadSceneMode mode)
    {
        bool targetSceneLoaded = scene.name == sceneToReplace.Value;
        if (targetSceneLoaded)
        {
            SceneManager.LoadScene(sceneToLoad.Value);
        }
    }
}
