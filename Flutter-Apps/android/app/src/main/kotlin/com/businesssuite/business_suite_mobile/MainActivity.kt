package com.businesssuite.business_suite_mobile

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "businesssuite/billing")
            .setMethodCallHandler { call, result ->
                if (call.method != "openBilling") {
                    result.notImplemented()
                    return@setMethodCallHandler
                }
                val origin = Uri.parse(call.argument<String>("origin").orEmpty())
                if (origin.scheme !in listOf("https", "http") || origin.host.isNullOrBlank()) {
                    result.error("INVALID_ORIGIN", "A valid BusinessSuite web address is required.", null)
                    return@setMethodCallHandler
                }
                val billing = origin.buildUpon().path("/srm/gst-billing").clearQuery().fragment(null).build()
                try {
                    startActivity(Intent(Intent.ACTION_VIEW, billing))
                    result.success(null)
                } catch (_: ActivityNotFoundException) {
                    result.error("NO_BROWSER", "No browser is available to open GST Billing.", null)
                }
            }
    }
}
