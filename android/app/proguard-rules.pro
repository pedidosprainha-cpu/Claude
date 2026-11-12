# kotlinx.serialization
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.**
-keepclassmembers class kotlinx.serialization.json.** { *** Companion; }
-keep,includedescriptorclasses class com.fxintel.app.data.**$$serializer { *; }
-keepclassmembers class com.fxintel.app.data.** { *** Companion; }
-keepclasseswithmembers class com.fxintel.app.data.** { kotlinx.serialization.KSerializer serializer(...); }
-keep class com.fxintel.app.data.** { *; }
# OkHttp
-dontwarn okhttp3.internal.platform.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**
