allprojects {
    repositories {
        // Optional machine-local cache for a checksum-verified Flutter engine.
        // Other SDK versions and dependencies continue using their normal repos.
        val localEngine = System.getenv("FLUTTER_LOCAL_ENGINE_MAVEN")
        if (localEngine != null) {
            val versionFile = file("$localEngine/engine.version")
            if (versionFile.isFile) {
                val engineVersion = versionFile.readText().trim()
                exclusiveContent {
                    forRepository { maven { url = uri(localEngine) } }
                    filter { includeVersion("io.flutter", "arm64_v8a_debug", engineVersion) }
                }
            }
        }
        google()
        mavenCentral()
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}
subprojects {
    project.evaluationDependsOn(":app")
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
