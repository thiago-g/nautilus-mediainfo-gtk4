# Nautilus Mediainfo GTK4 - A Nautilus extension that displays detailed metadata for multimedia files
# Copyright (C) 2018, Caldas Lopes    <joao.caldas.lopes@gmail.com> 
#               2025, Thiago Gobatto  <tggt@pm.me>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

#!/usr/bin/env python

import os
from MediaInfoDLL3 import *
from urllib.parse import unquote
from gi import require_version
require_version('Gtk', '4.0')
require_version('Nautilus', '4.0')
require_version('Notify', '0.7')
from gi.repository import Nautilus, GObject, Gtk, Gdk, Notify 

# Debugging toggle
DEBUG_MODE = False

def debug_print(message):
    if DEBUG_MODE:
        print(message)

class MediainfoExtension(GObject.GObject, Nautilus.MenuProvider):
    
    def __init__(self):
        super().__init__()
        self.exclude_list = ["METADATA_BLOCK_PICTURE"]

    def get_file_items_full(self, window, files, *args):
        debug_print("get_file_items_full called")
        if len(files) != 1 or files[0].get_uri_scheme() != 'file' or files[0].is_directory():
            return []

        file = files[0]
        filename = unquote(file.get_location().get_path())
        
        item = Nautilus.MenuItem(
            name="MediainfoExtension::mediainfo",
            label="Mediainfo",
            tip="Show media information"
        )
        item.connect('activate', self.on_mediainfo_activate, filename)
        debug_print(f"Adding context menu item for {filename}")
        return [item]

    def on_mediainfo_activate(self, menu, filename):
        MI = MediaInfo()
        MI.Option_Static("Complete")
        MI.Option_Static("Inform", "Nothing")
        MI.Open(filename)
        info = MI.Inform().splitlines()
        MI.Close()

        if len(info) < 8:
            return

        # Calculate window size based on screen resolution
        display = Gdk.Display.get_default()
        monitors = display.get_monitors()
        monitor = monitors.get_item(0)
        resolution = monitor.get_geometry()
        screen_width = resolution.width
        screen_height = resolution.height

        # Base resolution: 1920x1080, target size: 660x1040
        target_width = int(660 * (screen_width / 1920))
        target_height = int(1040 * (screen_height / 1080))

        # Create the GTK4 window to display the MediaInfo
        window = Gtk.Window(title="Mediainfo")
        window.set_default_size(target_width, target_height)
        window.set_transient_for(None)
        window.set_modal(True)
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        window.set_child(scrolled_window)

        # Grid layout to display information with padding
        grid = Gtk.Grid()
        grid.set_column_spacing(16)
        grid.set_row_spacing(4)
        grid.set_margin_start(10)  # Add left padding of 10 pixels
        grid.set_margin_top(10)  # Add space above the title
        scrolled_window.set_child(grid)

        top = 0
        for line in info:
            tag = line[:41].strip()
            value = line[42:].strip()

            # Check if the line is a section title
            if not value:
                # Create a section title with bigger font and bold
                title_label = Gtk.Label()
                title_label.set_can_focus(False)  # Disable focus
                title_label.set_markup(f"<span size='large'><b>{tag}</b></span>")
                title_label.set_halign(Gtk.Align.START)
                title_label.set_selectable(False)  # Disable text selection
                grid.attach(title_label, 0, top, 2, 1)  # Span across both columns
                top += 1

                # Add one spacer after the section title
                spacer_label = Gtk.Label()
                spacer_label.set_text("")  # Empty label to act as a spacer
                spacer_label.set_can_focus(False)  # Disable focus
                spacer_label.set_selectable(False)  # Disable text selection
                grid.attach(spacer_label, 0, top, 2, 1)  # Span across both columns
                top += 1
            else:
                # Create a regular label for the tag
                label = Gtk.Label()
                label.set_markup(f"<b>{tag}</b>")
                label.set_halign(Gtk.Align.START)
                label.set_can_focus(False)  # Disable focus
                label.set_selectable(False)  # Disable text selection
                grid.attach(label, 0, top, 1, 1)

                # Create a label for the value
                value_label = Gtk.Label()
                value_label.set_text(value)
                value_label.set_halign(Gtk.Align.START)
                value_label.set_selectable(True)  # Allow text selection for values
                value_label.set_wrap(True)
                value_label.set_can_focus(False)  # Disable focus
                grid.attach(value_label, 1, top, 1, 1)
                top += 1

        # Save button configuration
        save_button = Gtk.Button(label="Save to text file")
        save_button.set_halign(Gtk.Align.CENTER)  # Centered
        save_button.set_margin_top(20)
        save_button.set_margin_bottom(10)  # Add space at the bottom
        
        # Apply an Adwaita style using CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            button {
                border-radius: 12px;
                background: #007acc;
                color: white;
                padding: 8px 16px;
                font-weight: bold;
            }
            button:hover {
                background: #005f99;
            }
        """)
        style_context = save_button.get_style_context()
        style_context.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

        # Button Click
        save_button.connect("clicked", self.save_to_file, filename, info)

        # Place the button in the grid layout
        grid.attach(save_button, 0, top, 2, 1)  # Span across both columns
        grid.show()  

        # Get the preferred size of the grid
        requisition = grid.get_preferred_size()
        content_width = requisition.minimum_size.width
        content_height = requisition.minimum_size.height

        # Adjust the window size to fit the content, but not exceed the target size
        window_width = min(content_width + 40, target_width)  # Add some padding
        window_height = min(content_height + 40, target_height)  # Add some padding

        window.set_default_size(window_width, window_height)
        window.show()

    def save_to_file(self, button, filename, info):
        directory = os.path.dirname(filename)
        base_name = os.path.basename(filename)
        output_file = os.path.join(directory, f"{os.path.splitext(base_name)[0]}.txt")
        try:
            with open(output_file, 'w') as file:
                file.write("\n".join(info))
            debug_print(f"Output saved to {output_file}")

            # Show a GNOME Shell notification for success
            Notify.init("Mediainfo") 
            notification = Notify.Notification.new(
                "Output Saved", 
                f"File saved to:\n{output_file}",  
                "dialog-information"  # Use a standard info icon
            )
            notification.show()  

        except Exception as e:
            debug_print(f"Failed to save output: {e}")

            # Show a GNOME Shell notification for error
            Notify.init("Mediainfo")  
            notification = Notify.Notification.new(
                "Failed to Save",  
                f"Error: {str(e)}",  
                "dialog-error"  # Use a standard error icon
            )
            notification.show()  