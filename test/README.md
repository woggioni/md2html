## Overview
Envelope is a simple Gradle plugin that allows you to create an executable jar file
that includes all runtime dependencies and can be executed with a simple

```bash
java -jar my-app.jar
```
It supports JPMS, embedded system properties, Java agents, extra folders to be added to classpath. 

### Usage

Declare the plugin in your build's `settings.gradle` like this
```groovy

pluginManagement {
    repositories {
        maven {
            url = 'https://woggioni.net/mvn/'
        }
    }

    plugins {
        id "net.woggioni.gradle.envelope" version "2023.09.25"
    }
}
```

Then add it to a project's `build.gradle`

```groovy
plugins {
    id 'net.woggioni.gradle.envelope'
}

envelopeJar {
    mainClass = 'your.main.Class'
}
```

The plugin adds 2 tasks to your project:

- `envelopeJar` of type `net.woggioni.gradle.envelope.EnvelopeJarTask` that creates the executable jar in the project's libraries folder
- `envelopeRun` of type `org.gradle.api.tasks.JavaExec` which launches the jar created by the `envelopeJar` task

### Configuration

`EnvelopeJarTask` has several properties useful for configuration purposes:

###### mainClass 

This string property sets the class that will be searched for the `main` method to start the application

###### mainModule

When this string property is set, the jar file will be started in JPMS mode (if running on Java 9+) and 
this module will be searched for the main class, if the `mainClass` is not set the main class specified 
in the module descriptor will be loaded instead

###### systemProperties

This is a map that contains Java system properties that will be set before your application starts

###### extraClasspath

This is a list of strings representing filesystem paths that will be added to the classpath (if running in classpath mode) 
or to the module path (if running in JPMS mode) when the application starts. 

Relative paths and interpolation with Java System properties and environmental variables are supported:

e.g.

This looks for a `plugin` folder in the user's home directory
```
${env:HOME}/plugins
```

Same using Java system properties instead
```
${sys:user.home}/plugins
```

###### javaAgent
This is a method accepting 2 strings, the first is the Java agent classname and the second one is the java agent arguments.
It can be invoked multiple times to setup multiple java agents for the same JAR file. 
All the java agents will be invoked before the application startup.

### Example

```groovy
plugins {
    id 'net.woggioni.gradle.envelope'
}

envelopeJar {
    mainClass = 'your.main.Class'
    mainModule = 'your.main.module'

    systemProperties = [
        'some.property' : 'Some value'
    ]

    extraClasspath = ["plugins"]
    
    javaAgent('your.java.agent.Class', 'optional agent arguments')
}
```

### Limitations

This plugin requires Gradle >= 6.0 and Java >=0 8 to build the executable jar file.
The assembled envelope jar requires and Java >= 8 to run, if only `mainClass` is specified,
if both `mainModule` and `mainClass` are specified the generated jar file will (try to) run in classpath mode on Java 8
and in JPMS mode on Java > 8.

<object data="example.dot"/>
