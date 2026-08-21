package com.fetalguard.app;

import android.Manifest;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

import androidx.core.app.NotificationCompat;

import com.getcapacitor.JSObject;
import com.getcapacitor.PermissionState;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;

@CapacitorPlugin(
    name = "PatientNotifications",
    permissions = {
        @Permission(alias = "notifications", strings = { Manifest.permission.POST_NOTIFICATIONS })
    }
)
public class PatientNotificationsPlugin extends Plugin {
    private static final String SOUND_CHANNEL_ID = "patient_alerts_sound";
    private static final String SILENT_CHANNEL_ID = "patient_alerts_silent";

    @PluginMethod
    public void show(PluginCall call) {
        String title = call.getString("title", "FETAL-GUARD");
        String body = call.getString("body");
        Integer notificationId = call.getInt("id", 1);
        boolean sound = Boolean.TRUE.equals(call.getBoolean("sound", false));
        if (body == null || body.trim().isEmpty()) {
            call.reject("notification_body_required");
            return;
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
            && getPermissionState("notifications") != PermissionState.GRANTED) {
            call.reject("notification_permission_denied");
            return;
        }

        Context context = getContext();
        NotificationManager manager = (NotificationManager) context.getSystemService(
            Context.NOTIFICATION_SERVICE
        );
        String channelId = sound ? SOUND_CHANNEL_ID : SILENT_CHANNEL_ID;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            int importance = sound
                ? NotificationManager.IMPORTANCE_HIGH
                : NotificationManager.IMPORTANCE_LOW;
            NotificationChannel channel = new NotificationChannel(
                channelId,
                sound ? "FETAL-GUARD alerts" : "FETAL-GUARD silent alerts",
                importance
            );
            channel.setDescription("Patient monitoring notifications received by the application");
            channel.enableVibration(false);
            if (!sound) channel.setSound(null, null);
            manager.createNotificationChannel(channel);
        }

        Intent intent = new Intent(context, MainActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent pendingIntent = PendingIntent.getActivity(
            context,
            notificationId,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
        NotificationCompat.Builder builder = new NotificationCompat.Builder(context, channelId)
            .setSmallIcon(R.drawable.ic_stat_fetal_guard)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(new NotificationCompat.BigTextStyle().bigText(body))
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .setPriority(sound ? NotificationCompat.PRIORITY_HIGH : NotificationCompat.PRIORITY_LOW)
            .setSilent(!sound);
        manager.notify(notificationId, builder.build());

        JSObject result = new JSObject();
        result.put("delivered", true);
        call.resolve(result);
    }
}
