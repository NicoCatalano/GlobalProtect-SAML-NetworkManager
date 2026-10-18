/* Headless GTK round-trip check. Build once for each GTK major and run with
 * GDK_BACKEND=broadway (or under Xvfb). Never load a real NM connection. */
#ifdef TEST_GTK4
#include "../plugins/gnome/nm-gpclient-editor.c"
#else
#include "../plugins/gnome/nm-gpclient-editor-gtk3.c"
#endif

int main (void)
{
#if GTK_MAJOR_VERSION >= 4
    gtk_init ();
#else
    gtk_init (NULL, NULL);
#endif
    const char *values[] = { NULL, "false", "true", "invalid" };
    for (unsigned int i = 0; i < G_N_ELEMENTS (values); i++) {
        NMConnection *connection = nm_simple_connection_new ();
        NMSettingVpn *vpn = NM_SETTING_VPN (nm_setting_vpn_new ());
        g_object_set (vpn, NM_SETTING_VPN_SERVICE_TYPE,
                      "org.freedesktop.NetworkManager.gpclient", NULL);
        nm_setting_vpn_add_data_item (vpn, "gateway", "vpn.example.invalid");
        if (values[i])
            nm_setting_vpn_add_data_item (vpn, "close-browser", values[i]);
        nm_connection_add_setting (connection, NM_SETTING (vpn));
        NMGpclientEditor *editor = nm_gpclient_editor_new (connection);
        GtkWidget *view = GTK_WIDGET (nm_vpn_editor_get_widget (NM_VPN_EDITOR (editor)));
        g_assert_true (GTK_IS_SCROLLED_WINDOW (view));
#if GTK_MAJOR_VERSION >= 4
        g_assert_cmpint (gtk_check_button_get_active (GTK_CHECK_BUTTON (editor->close_browser_check)),
                        ==, g_strcmp0 (values[i], "true") == 0);
#else
        g_assert_cmpint (gtk_toggle_button_get_active (GTK_TOGGLE_BUTTON (editor->close_browser_check)),
                        ==, g_strcmp0 (values[i], "true") == 0);
#endif
        for (int checked = 1; checked >= 0; checked--) {
#if GTK_MAJOR_VERSION >= 4
            gtk_check_button_set_active (GTK_CHECK_BUTTON (editor->close_browser_check), checked);
#else
            gtk_toggle_button_set_active (GTK_TOGGLE_BUTTON (editor->close_browser_check), checked);
#endif
            GError *error = NULL;
            g_assert_true (nm_vpn_editor_update_connection (NM_VPN_EDITOR (editor), connection, &error));
            g_assert_no_error (error);
            g_assert_cmpstr (nm_setting_vpn_get_data_item (nm_connection_get_setting_vpn (connection),
                                                         "close-browser"), ==, checked ? "true" : "false");
        }
        g_assert_cmpint (gtk_scrolled_window_get_min_content_width (GTK_SCROLLED_WINDOW (view)), >=, 660);
        g_object_unref (editor);
        g_object_unref (connection);
    }
    g_print ("GTK%d: checkbox defaults, true/false round trips and scroll layout passed\n", GTK_MAJOR_VERSION);
    return 0;
}
