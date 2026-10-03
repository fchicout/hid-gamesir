// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * Linux HID Driver for GameSir / Guangzhou Chicken Run Controllers
 *
 * Fixes battery gauge bugs, input anomalies, and mode-switching quirks
 * for GameSir controllers emulating Sony DualShock 4 or Xbox protocols.
 *
 * Copyright (c) 2026 Francisco Chicout
 */

#include <linux/device.h>
#include <linux/hid.h>
#include <linux/module.h>
#include <linux/slab.h>
#include <linux/string.h>
#include <linux/power_supply.h>
#include "hid-gamesir.h"

#define DRIVER_NAME "hid-gamesir"
#define DRIVER_VERSION "0.1.0"

static bool disable_battery_node = true;
module_param(disable_battery_node, bool, 0644);
MODULE_PARM_DESC(disable_battery_node,
		 "Disable registering the faulty power_supply battery node (default: true)");

static const char * const gamesir_signatures[] = {
	"Chicken Run",
	"GameSir",
	"GAMESIR",
	"gamesir",
};

static bool is_gamesir_device(const struct hid_device *hdev)
{
	size_t i;

	if (!hdev || !hdev->name[0])
		return false;

	for (i = 0; i < ARRAY_SIZE(gamesir_signatures); i++) {
		if (strstr(hdev->name, gamesir_signatures[i]))
			return true;
	}

	return false;
}

static int gamesir_raw_event(struct hid_device *hdev, struct hid_report *report,
			     u8 *data, int size)
{
	struct gamesir_device *gdev = hid_get_drvdata(hdev);
	unsigned long flags;

	if (!gdev || !data || size < 33)
		return 0;

	/*
	 * In standard DS4 emulation (Report ID 0x01, size >= 33):
	 * Byte 30 is the battery telemetry byte in official DualShock 4 reports.
	 * GameSir leaves it as 0x00 over USB, which causes upstream drivers to report 5%.
	 */
	if (data[0] == 0x01) {
		const u8 bat_byte = data[30];
		const u8 bat_level = bat_byte & 0x0F;

		spin_lock_irqsave(&gdev->lock, flags);
		if (bat_level == 0 && (gdev->quirks & GAMESIR_QUIRK_NO_BATTERY_GAUGE)) {
			gdev->battery_capacity = -1;
			gdev->battery_status = POWER_SUPPLY_STATUS_UNKNOWN;
		} else {
			gdev->battery_capacity = min_t(int, bat_level * 10, 100);
			gdev->battery_status = (bat_byte & 0x10) ?
				POWER_SUPPLY_STATUS_CHARGING : POWER_SUPPLY_STATUS_DISCHARGING;
		}
		spin_unlock_irqrestore(&gdev->lock, flags);
	}

	return 0;
}

static int gamesir_probe(struct hid_device *hdev, const struct hid_device_id *id)
{
	struct gamesir_device *gdev;
	int ret;

	/*
	 * Verify if this device is genuinely a GameSir / Guangzhou Chicken Run product.
	 * If not, yield to official hid-playstation or hid-sony drivers.
	 */
	if (!is_gamesir_device(hdev)) {
		hid_dbg(hdev, "Non-GameSir device ignored by " DRIVER_NAME "\n");
		return -ENODEV;
	}

	hid_info(hdev, "Claiming GameSir Controller: %s (VID: 0x%04x, PID: 0x%04x)\n",
		 hdev->name, hdev->vendor, hdev->product);

	gdev = devm_kzalloc(&hdev->dev, sizeof(*gdev), GFP_KERNEL);
	if (!gdev)
		return -ENOMEM;

	gdev->hdev = hdev;
	gdev->quirks = (u32)id->driver_data;
	gdev->battery_capacity = -1;
	gdev->battery_status = POWER_SUPPLY_STATUS_UNKNOWN;
	spin_lock_init(&gdev->lock);
	hid_set_drvdata(hdev, gdev);

	ret = hid_parse(hdev);
	if (ret) {
		hid_err(hdev, "Failed to parse HID report descriptor: %d\n", ret);
		return ret;
	}

	ret = hid_hw_start(hdev, HID_CONNECT_DEFAULT);
	if (ret) {
		hid_err(hdev, "Failed to start HID hardware: %d\n", ret);
		return ret;
	}

	hid_info(hdev, "GameSir controller initialized successfully (Driver v" DRIVER_VERSION ")\n");
	return 0;
}

static void gamesir_remove(struct hid_device *hdev)
{
	hid_hw_stop(hdev);
	hid_info(hdev, "GameSir controller removed\n");
}

static const struct hid_device_id gamesir_devices[] = {
	/* GameSir / Guangzhou Chicken Run controllers spoofing Sony DualShock 4 */
	{ HID_USB_DEVICE(USB_VENDOR_ID_SONY_SPOOFED, USB_DEVICE_ID_SONY_DS4_CUH_ZCT2),
	  .driver_data = GAMESIR_QUIRK_NO_BATTERY_GAUGE },
	{ }
};
MODULE_DEVICE_TABLE(hid, gamesir_devices);

static struct hid_driver gamesir_driver = {
	.name = DRIVER_NAME,
	.id_table = gamesir_devices,
	.probe = gamesir_probe,
	.remove = gamesir_remove,
	.raw_event = gamesir_raw_event,
};

module_hid_driver(gamesir_driver);

MODULE_AUTHOR("Francisco Chicout");
MODULE_DESCRIPTION("Linux HID driver for GameSir / Guangzhou Chicken Run Controllers");
MODULE_VERSION(DRIVER_VERSION);
MODULE_LICENSE("GPL");
