import logging
import re
import utils

re_sub = re.compile(r"\s+")

re_patterns = {
    "bssid": re.compile(r"Address: *([0-9A-F:]+)"),
    "channel": re.compile(r"Channel: *(\d+)"),
    "freq": re.compile(r"Frequency: *([\d\.]+ ?.Hz)"),
    "rssi": re.compile(r"Signal level= *([-\d\.]+ ?dBm)"),
    "ssid": re.compile(r"ESSID: *\"([^\"]+)\""),
    "rates": re.compile(r"\d+ Mb/s"),
    "extras": re.compile(r"IE: +Unknown: +([0-9A-F]+)")
}

re_tx_bitrate = re.compile(r"tx bitrate: *(.+)")
re_rx_bitrate = re.compile(r"rx bitrate: *(.+)")
re_timestamp = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2},\d+[+-]\d{2}:\d{2}")
re_link_rssi = re.compile(r"signal: *([-\d\.]+ ?dBm)")


def byte_uint_to_int(byte_uint):
    out = byte_uint
    # check sign bit
    if (out & 0x8000) == 0x8000:
        # if set, invert and add one to get the negative value,
        # then add the negative sign
        out = -((out ^ 0xffff) + 1)
    return out


def read_beacon_ie(ie_hex_string):
    output = {
        "id": 0,
        "raw": ie_hex_string,
        "type": "Unknown",
        "elements": {}
    }
    # Convert hex string to bytes
    byte_data = bytes.fromhex(ie_hex_string)
    output["id"] = byte_data[0]
    # Bytes are read from lowest index, example: [0x00, 0xFF, 0x1A]
    # In wireshark becomes: 0x1AFF00

    try:
        match output["id"]:
            case 11:
                # BSS Load
                output["type"] = "BSS Load"
                output["elements"]["sta_count"] = int.from_bytes(
                    byte_data[2:4], byteorder='little')
                output["elements"]["ch_utilization"] = byte_data[4] / 255
                output["elements"]["available_admission_cap"] = int.from_bytes(
                    byte_data[5:7], byteorder='little')

            case 35:
                # TPC Report
                output["type"] = "TPC Report"
                output["elements"]["tx_power"] = byte_uint_to_int(byte_data[2])
                output["elements"]["link_margin"] = byte_uint_to_int(byte_data[3])

            case 45:
                # HT Capabilities
                output["type"] = "HT Capabilities"

                ht_caps_info = byte_data[2:4]
                output["elements"]["ht_ldpc_coding_capability"] = (
                    (ht_caps_info[0]) & 0x01)
                output["elements"]["ht_support_channel_width"] = (
                    (ht_caps_info[0] >> 1) & 0x01)
                output["elements"]["ht_sm_power_save"] = (
                    (ht_caps_info[0] >> 2) & 0x03)
                output["elements"]["ht_green_field"] = (
                    (ht_caps_info[0] >> 4) & 0x01)
                output["elements"]["ht_short_gi_for_20mhz"] = (
                    (ht_caps_info[0] >> 5) & 0x01)
                output["elements"]["ht_short_gi_for_40mhz"] = (
                    (ht_caps_info[0] >> 6) & 0x01)
                output["elements"]["ht_tx_stbc"] = (
                    (ht_caps_info[0] >> 7) & 0x01)
                output["elements"]["ht_rx_stbc"] = (
                    (ht_caps_info[1]) & 0x03)
                output["elements"]["ht_delayed_block_ack"] = (
                    (ht_caps_info[1] >> 2) & 0x01)
                output["elements"]["ht_max_a_msdu_length"] = (
                    (ht_caps_info[1] >> 3) & 0x01)
                output["elements"]["ht_dsss_cck_mode_in_40mhz"] = (
                    (ht_caps_info[1] >> 4) & 0x01)
                output["elements"]["ht_psmp_support"] = (
                    (ht_caps_info[1] >> 5) & 0x01)
                output["elements"]["ht_forty_mhz_intolerant"] = (
                    (ht_caps_info[1] >> 6) & 0x01)
                output["elements"]["ht_l_sig_txop_protection_support"] = (
                    (ht_caps_info[1] >> 7) & 0x01)

                ampdu_param = byte_data[4]
                output["elements"]["maximum_rx_a_mpdu_length"] = (
                    (ampdu_param) & 0x03)
                output["elements"]["mpdu_density"] = (
                    (ampdu_param >> 2) & 0x07)

                ht_mcs_set = byte_data[5:21]
                output["elements"]["rx_mcs_bitmask"] = int.from_bytes(
                    ht_mcs_set[0:10], byteorder='little')
                output["elements"]["rx_highest_supported_rate"] = (
                    (ht_mcs_set[10])
                    + ((ht_mcs_set[11] & 0x03) << 8))
                output["elements"]["tx_mcs_set_defined"] = (
                    (ht_mcs_set[12]) & 0x01)
                output["elements"]["tx_rx_mcs_set_not_equal"] = (
                    (ht_mcs_set[12] >> 1) & 0x01)
                output["elements"]["tx_max_ss_supported"] = (
                    (ht_mcs_set[12] >> 2) & 0x03)
                output["elements"]["tx_unequal_modulation_supported"] = (
                    (ht_mcs_set[12] >> 4) & 0x01)

                ht_ext_caps = byte_data[21:23]
                output["elements"]["transmitter_supports_pco"] = (
                    (ht_ext_caps[0]) & 0x01)
                output["elements"]["time_needed_to_transition_between_20mhz_and_40mhz"] = (
                    (ht_ext_caps[0] >> 1) & 0x03)
                output["elements"]["mcs_feedback_capability"] = (
                    (ht_ext_caps[1]) & 0x03)
                output["elements"]["high_throughput"] = (
                    (ht_ext_caps[1] >> 2) & 0x01)
                output["elements"]["reverse_direction_responder"] = (
                    (ht_ext_caps[1] >> 3) & 0x01)

                txbf_caps = byte_data[23:27]
                output["elements"]["transmit_beamforming"] = (
                    (txbf_caps[0]) & 0x01)
                output["elements"]["receive_staggered_sounding"] = (
                    (txbf_caps[0] >> 1) & 0x01)
                output["elements"]["transmit_staggered_sounding"] = (
                    (txbf_caps[0] >> 2) & 0x01)
                output["elements"]["receive_null_data_packet_(ndp)"] = (
                    (txbf_caps[0] >> 3) & 0x01)
                output["elements"]["transmit_null_data_packet_(ndp)"] = (
                    (txbf_caps[0] >> 4) & 0x01)
                output["elements"]["implicit_txbf_capable"] = (
                    (txbf_caps[0] >> 5) & 0x01)
                output["elements"]["calibration"] = (
                    (txbf_caps[0] >> 6) & 0x03)
                output["elements"]["sta_can_apply_txbf_using_csi_explicit_feedback"] = (
                    (txbf_caps[1]) & 0x01)
                output["elements"]["sta_can_apply_txbf_using_uncompressed_beamforming_feedback_matrix"] = (
                    (txbf_caps[1] >> 1) & 0x01)
                output["elements"]["sta_can_apply_txbf_using_compressed_beamforming_feedback_matrix"] = (
                    (txbf_caps[1] >> 2) & 0x01)
                output["elements"]["receiver_can_return_explicit_csi_feedback"] = (
                    (txbf_caps[1] >> 3) & 0x03)
                output["elements"]["receiver_can_return_explicit_uncompressed_beamforming_feedback_matrix"] = (
                    (txbf_caps[1] >> 5) & 0x03)
                output["elements"]["sta_can_compress_and_use_compressed_beamforming_feedback_matrix"] = (
                    ((txbf_caps[1] >> 7) & 0x01)
                    + ((txbf_caps[2] & 0x01) << 1))
                output["elements"]["minimal_grouping_used_for_explicit_feedback_reports"] = (
                    (txbf_caps[2] >> 1) & 0x03)
                output["elements"]["max_antennae_sta_can_support_when_csi_feedback_required"] = (
                    (txbf_caps[2] >> 3) & 0x03)
                output["elements"]["max_antennae_sta_can_support_when_uncompressed_beamforming_feedback_required"] = (
                    (txbf_caps[2] >> 5) & 0x03)
                output["elements"]["max_antennae_sta_can_support_when_compressed_beamforming_feedback_required"] = (
                    ((txbf_caps[2] >> 7) & 0x01)
                    + ((txbf_caps[3] & 0x01) << 1))
                output["elements"]["maximum_number_of_rows_of_csi_explicit_feedback"] = (
                    (txbf_caps[3] >> 1) & 0x03)
                output["elements"]["maximum_number_of_space_time_streams_for_which_channel_dimensions_can_be_simultaneously_estimated"] = (
                    (txbf_caps[3] >> 3) & 0x03)

                asel_caps = byte_data[27]
                output["elements"]["antenna_selection_capable"] = (
                    (asel_caps) & 0x01)
                output["elements"]["explicit_csi_feedback_based_tx_asel"] = (
                    (asel_caps >> 1) & 0x01)
                output["elements"]["antenna_indices_feedback_based_tx_asel"] = (
                    (asel_caps >> 2) & 0x01)
                output["elements"]["explicit_csi_feedback"] = (
                    (asel_caps >> 3) & 0x01)
                output["elements"]["antenna_indices_feedback"] = (
                    (asel_caps >> 4) & 0x01)
                output["elements"]["rx_asel"] = (
                    (asel_caps >> 5) & 0x01)
                output["elements"]["tx_sounding_ppdus"] = (
                    (asel_caps >> 6) & 0x01)

            case 61:
                # HT Operation
                output["type"] = "HT Operation"
                output["elements"]["primary_channel"] = byte_data[2]

                ht_operation_info = byte_data[3:8]
                output["elements"]["secondary_channel_offset"] = (
                    ht_operation_info[0] & 0x03)
                output["elements"]["sta_channel_width"] = (
                    (ht_operation_info[0] >> 2) & 0x01)
                output["elements"]["rifs_mode"] = (
                    (ht_operation_info[0] >> 3) & 0x01)
                output["elements"]["ht_protection"] = (
                    ht_operation_info[1] & 0x03)
                output["elements"]["nongf_ht_sta_present"] = (
                    (ht_operation_info[1] >> 2) & 0x01)
                output["elements"]["obss_nonht_sta_present"] = (
                    (ht_operation_info[1] >> 4) & 0x01)
                output["elements"]["channel_center_freq_segment_2"] = (
                    ((ht_operation_info[1] >> 5) & 0x07)
                    + ((ht_operation_info[2] & 0x1F) << 3))
                output["elements"]["dual_beacon"] = (
                    (ht_operation_info[3] >> 6) & 0x01)
                output["elements"]["dual_cts_protection"] = (
                    (ht_operation_info[3] >> 7) & 0x01)
                output["elements"]["stbc_beacon"] = (
                    ht_operation_info[4] & 0x01)
                output["elements"]["lsig_txop_protection"] = (
                    (ht_operation_info[4] >> 1) & 0x01)
                output["elements"]["pco_active"] = (
                    (ht_operation_info[4] >> 2) & 0x01)
                output["elements"]["pco_phase"] = (
                    (ht_operation_info[4] >> 3) & 0x01)

                ht_mcs_set = byte_data[8:24]
                output["elements"]["rx_mcs_bitmask"] = int.from_bytes(
                    ht_mcs_set[0:10], byteorder='little')
                output["elements"]["rx_highest_supported_rate"] = (
                    (ht_mcs_set[10])
                    + ((ht_mcs_set[11] & 0x03) << 8))
                output["elements"]["tx_mcs_set_defined"] = (
                    (ht_mcs_set[12]) & 0x01)
                output["elements"]["tx_rx_mcs_set_not_equal"] = (
                    (ht_mcs_set[12] >> 1) & 0x01)
                output["elements"]["tx_max_ss_supported"] = (
                    (ht_mcs_set[12] >> 2) & 0x03)
                output["elements"]["tx_unequal_modulation_supported"] = (
                    (ht_mcs_set[12] >> 4) & 0x01)

            case 133:
                # Cisco CCX1 CKIP + Device name
                # 1 ID | 1 len | 10 unknown | 15 device name | 2 num clients | 3 unknown
                output["type"] = "Cisco CCX1 CKIP"
                output["elements"]["ap_name"] = byte_data[12:27].decode('utf-8')
                output["elements"]["sta_count"] = int.from_bytes(
                    byte_data[27:29], byteorder='little')

            case 191:
                # VHT Capabilities
                output["type"] = "VHT Capabilities"

                vht_caps_info = byte_data[2:6]
                output["elements"]["maximum_mpdu_length"] = (
                    (vht_caps_info[0]) & 0x03)
                output["elements"]["supported_channel_width_set"] = (
                    (vht_caps_info[0] >> 2) & 0x03)
                output["elements"]["rx_ldpc"] = (
                    (vht_caps_info[0] >> 4) & 0x01)
                output["elements"]["short_gi_for_80mhz_tvht_mode_4c"] = (
                    (vht_caps_info[0] >> 5) & 0x01)
                output["elements"]["short_gi_for_160mhz_and_80+80mhz"] = (
                    (vht_caps_info[0] >> 6) & 0x01)
                output["elements"]["tx_stbc"] = (
                    (vht_caps_info[0] >> 7) & 0x01)
                output["elements"]["rx_stbc"] = (
                    (vht_caps_info[1]) & 0x07)
                output["elements"]["su_beamformer_capable"] = (
                    (vht_caps_info[1] >> 3) & 0x01)
                output["elements"]["su_beamformee_capable"] = (
                    (vht_caps_info[1] >> 4) & 0x01)
                output["elements"]["beamformee_sts_capability"] = (
                    (vht_caps_info[1] >> 5) & 0x07)
                output["elements"]["number_of_sounding_dimensions"] = (
                    (vht_caps_info[2]) & 0x07)
                output["elements"]["mu_beamformer_capable"] = (
                    (vht_caps_info[2] >> 3) & 0x01)
                output["elements"]["mu_beamformee_capable"] = (
                    (vht_caps_info[2] >> 4) & 0x01)
                output["elements"]["txop_ps"] = (
                    (vht_caps_info[2] >> 5) & 0x01)
                output["elements"]["+htc_vht_capable"] = (
                    (vht_caps_info[2] >> 6) & 0x01)
                output["elements"]["max_a_mpdu_length_exponent"] = (
                    ((vht_caps_info[2] >> 7) & 0x01)
                    + ((vht_caps_info[3] & 0x03) << 1))
                output["elements"]["vht_link_adaptation"] = (
                    (vht_caps_info[3] >> 2) & 0x03)
                output["elements"]["rx_antenna_pattern_consistency"] = (
                    (vht_caps_info[3] >> 4) & 0x01)
                output["elements"]["tx_antenna_pattern_consistency"] = (
                    (vht_caps_info[3] >> 5) & 0x01)
                output["elements"]["extended_nss_bw_support"] = (
                    (vht_caps_info[3] >> 6) & 0x03)

                vht_mcs_set = byte_data[6:14]
                output["elements"]["supported_rx_mcs_set"] = int.from_bytes(
                    vht_mcs_set[0:2], byteorder="little")
                output["elements"]["rx_highest_long_gi_data_rate"] = (
                    (vht_mcs_set[2])
                    + ((vht_mcs_set[3] & 0x1F) << 8))
                output["elements"]["max_nsts_total"] = (
                    (vht_caps_info[3] >> 5) & 0x07)
                output["elements"]["supported_tx_mcs_set"] = int.from_bytes(
                    vht_mcs_set[4:6], byteorder="little")
                output["elements"]["tx_highest_long_gi_data_rate_"] = (
                    (vht_mcs_set[6])
                    + ((vht_mcs_set[7] & 0x1F) << 8))
                output["elements"]["extended_nss_bw_capable"] = (
                    (vht_mcs_set[7] >> 5) & 0x01)

            case 192:
                # VHT Operation
                output["type"] = "VHT Operation"
                output["elements"]["channel_width"] = byte_data[2]
                output["elements"]["channel_center_freq_0"] = byte_data[3]
                output["elements"]["channel_center_freq_1"] = byte_data[4]
                output["elements"]["basic_mcs_set"] = int.from_bytes(
                    byte_data[5:7], byteorder='little')

            case 221:
                # Vendor specific
                # 1 ID | 1 Len | 3 OUI | 1 OUI Type | vendor specific payload
                output["type"] = "Vendor Specific"
                output["elements"]["oui"] = byte_data[2:5].hex().lower()
                output["elements"]["oui_type"] = byte_data[5]

                if (output["elements"]["oui"] == "000b86"):
                    output["elements"]["vendor_name"] = "Aruba"
                    # Only Aruba have subtype
                    output["elements"]["oui_subtype"] = byte_data[6]
                    if (output["elements"]["oui_type"] == 1
                            and output["elements"]["oui_subtype"] == 3):
                        # Skip byte_data[7] since it's always 0x00
                        output["elements"]["ap_name"] = byte_data[8:].decode(
                            'utf-8')
                elif (output["elements"]["oui"] == "8cfdf0"):
                    output["elements"]["vendor_name"] = "Qualcomm"
                elif (output["elements"]["oui"] == "0050f2"):
                    output["elements"]["vendor_name"] = "Microsoft"
                elif (output["elements"]["oui"] == "506f9a"):
                    output["elements"]["vendor_name"] = "Wi-Fi Alliance"
                    if (output["elements"]["oui_type"] == 28):
                        output["elements"]["bssid"] = utils.hex_to_bssid(
                            byte_data[6:12].hex())
                        # Skip byte_data[12] = SSID length
                        output["elements"]["ssid"] = byte_data[13:].decode(
                            'utf-8')

            case 255:
                output["elements"]["ext_id"] = byte_data[2]
                match output["elements"]["ext_id"]:
                    case 35:
                        # HE Capabilities
                        output["type"] = "HE Capabilities"

                        he_mac_info = byte_data[3:9]
                        output["elements"]["+htc_he_support"] = (
                            (he_mac_info[0]) & 0x01)
                        output["elements"]["twt_requester_support"] = (
                            (he_mac_info[0] >> 1) & 0x01)
                        output["elements"]["twt_responder_support"] = (
                            (he_mac_info[0] >> 2) & 0x01)
                        output["elements"]["dynamic_fragmentation_support"] = (
                            (he_mac_info[0] >> 3) & 0x03)
                        output["elements"]["trigger_frame_mac_padding_duration"] = (
                            (he_mac_info[1] >> 2) & 0x03)
                        output["elements"]["multi_tid_aggregation_rx_support"] = (
                            (he_mac_info[1] >> 4) & 0x07)
                        output["elements"]["he_link_adaptation_support"] = (
                            ((he_mac_info[1] >> 7) & 0x01)
                            + ((he_mac_info[2] & 0x01) << 1))
                        output["elements"]["all_ack_support"] = (
                            (he_mac_info[2] >> 1) & 0x01)
                        output["elements"]["trs_support"] = (
                            (he_mac_info[2] >> 2) & 0x01)
                        output["elements"]["bsr_support"] = (
                            (he_mac_info[2] >> 3) & 0x01)
                        output["elements"]["broadcast_twt_support"] = (
                            (he_mac_info[2] >> 4) & 0x01)
                        output["elements"]["32_bit_ba_bitmap_support"] = (
                            (he_mac_info[2] >> 5) & 0x01)
                        output["elements"]["mu_cascading_support"] = (
                            (he_mac_info[2] >> 6) & 0x01)
                        output["elements"]["ack_enabled_aggregation_support"] = (
                            (he_mac_info[2] >> 7) & 0x01)
                        output["elements"]["om_control_support"] = (
                            (he_mac_info[3] >> 1) & 0x01)
                        output["elements"]["ofdma_ra_support"] = (
                            (he_mac_info[3] >> 2) & 0x01)
                        output["elements"]["maximum_a_mpdu_length_exponent_extension"] = (
                            (he_mac_info[3] >> 3) & 0x03)
                        output["elements"]["flexible_twt_schedule_support"] = (
                            (he_mac_info[3] >> 6) & 0x01)
                        output["elements"]["rx_control_frame_to_multibss"] = (
                            (he_mac_info[3] >> 7) & 0x01)
                        output["elements"]["bsrp_bqrp_a_mpdu_aggregation"] = (
                            (he_mac_info[4]) & 0x01)
                        output["elements"]["qtp_support"] = (
                            (he_mac_info[4] >> 1) & 0x01)
                        output["elements"]["bqr_support"] = (
                            (he_mac_info[4] >> 2) & 0x01)
                        output["elements"]["psr_responder"] = (
                            (he_mac_info[4] >> 3) & 0x01)
                        output["elements"]["ndp_feedback_report_support"] = (
                            (he_mac_info[4] >> 4) & 0x01)
                        output["elements"]["ops_support"] = (
                            (he_mac_info[4] >> 5) & 0x01)
                        output["elements"]["a_msdu_not_under_ba_in_ack_enabled_a_mpdu_support"] = (
                            (he_mac_info[4] >> 6) & 0x01)
                        output["elements"]["multi_tid_aggregation_tx_support"] = (
                            ((he_mac_info[4] >> 7) & 0x01)
                            + ((he_mac_info[5] & 0x03) << 1))
                        output["elements"]["he_subchannel_selective_transmission_support"] = (
                            (he_mac_info[5] >> 2) & 0x01)
                        output["elements"]["ul_2x996_tone_ru_support"] = (
                            (he_mac_info[5] >> 3) & 0x01)
                        output["elements"]["om_control_ul_mu_data_disable_rx_support"] = (
                            (he_mac_info[5] >> 4) & 0x01)
                        output["elements"]["he_dynamic_sm_power_save"] = (
                            (he_mac_info[5] >> 5) & 0x01)
                        output["elements"]["punctured_sounding_support"] = (
                            (he_mac_info[5] >> 6) & 0x01)
                        output["elements"]["ht_and_vht_trigger_frame_rx_support"] = (
                            (he_mac_info[5] >> 7) & 0x01)

                        he_phy_info = byte_data[9:20]
                        output["elements"]["channel_width_set"] = (
                            (he_phy_info[0] >> 1) & 0x7F)
                        output["elements"]["punctured_preamble_rx"] = (
                            (he_phy_info[1]) & 0x0F)
                        output["elements"]["device_class"] = (
                            (he_phy_info[1] >> 4) & 0x01)
                        output["elements"]["ldpc_coding_in_payload"] = (
                            (he_phy_info[1] >> 5) & 0x01)
                        output["elements"]["he_su_ppdu_with_1x_he_ltf_and_0.8us_gi"] = (
                            (he_phy_info[1] >> 6) & 0x01)
                        output["elements"]["midamble_tx_rx_max_nsts"] = (
                            ((he_phy_info[1] >> 7) & 0x01)
                            + ((he_phy_info[2] & 0x01) << 1))
                        output["elements"]["ndp_with_4x_he_ltf_and_3.2us_gi"] = (
                            (he_phy_info[2] >> 1) & 0x01)
                        output["elements"]["stbc_tx_<=_80mhz"] = (
                            (he_phy_info[2] >> 2) & 0x01)
                        output["elements"]["stbc_rx_<=_80mhz"] = (
                            (he_phy_info[2] >> 3) & 0x01)
                        output["elements"]["doppler_tx"] = (
                            (he_phy_info[2] >> 4) & 0x01)
                        output["elements"]["doppler_rx"] = (
                            (he_phy_info[2] >> 5) & 0x01)
                        output["elements"]["full_bandwidth_ul_mu_mimo"] = (
                            (he_phy_info[2] >> 6) & 0x01)
                        output["elements"]["partial_bandwidth_ul_mu_mimo"] = (
                            (he_phy_info[2] >> 7) & 0x01)

                        output["elements"]["dcm_max_constellation_tx"] = (
                            (he_phy_info[3]) & 0x03)
                        output["elements"]["dcm_max_nss_tx"] = (
                            (he_phy_info[3] >> 2) & 0x01)
                        output["elements"]["dcm_max_constellation_rx"] = (
                            (he_phy_info[3] >> 3) & 0x03)
                        output["elements"]["dcm_max_nss_rx"] = (
                            (he_phy_info[3] >> 5) & 0x01)
                        output["elements"]["rx_partial_bw_su_in_20mhz_he_mu_ppdu"] = (
                            (he_phy_info[3] >> 6) & 0x01)
                        output["elements"]["su_beamformer"] = (
                            (he_phy_info[3] >> 7) & 0x01)

                        output["elements"]["su_beamformee"] = (
                            (he_phy_info[4]) & 0x01)
                        output["elements"]["mu_beamformer"] = (
                            (he_phy_info[4] >> 1) & 0x01)
                        output["elements"]["beamformee_sts_<=_80mhz"] = (
                            (he_phy_info[4] >> 2) & 0x07)
                        output["elements"]["beamformee_sts_>_80mhz"] = (
                            (he_phy_info[4] >> 5) & 0x07)

                        output["elements"]["number_of_sounding_dimensions_<=_80mhz"] = (
                            (he_phy_info[5]) & 0x07)
                        output["elements"]["number_of_sounding_dimensions_>_80mhz"] = (
                            (he_phy_info[5] >> 3) & 0x07)
                        output["elements"]["ng_=_16_su_feedback"] = (
                            (he_phy_info[5] >> 6) & 0x01)
                        output["elements"]["ng_=_16_mu_feedback"] = (
                            (he_phy_info[5] >> 7) & 0x01)

                        output["elements"]["codebook_size_su_feedback"] = (
                            (he_phy_info[6]) & 0x01)
                        output["elements"]["codebook_size_mu_feedback"] = (
                            (he_phy_info[6] >> 1) & 0x01)
                        output["elements"]["triggered_su_beamforming_feedback"] = (
                            (he_phy_info[6] >> 2) & 0x01)
                        output["elements"]["triggered_mu_beamforming_feedback"] = (
                            (he_phy_info[6] >> 3) & 0x01)
                        output["elements"]["triggered_cqi_feedback"] = (
                            (he_phy_info[6] >> 4) & 0x01)
                        output["elements"]["partial_bandwidth_extended_range"] = (
                            (he_phy_info[6] >> 5) & 0x01)
                        output["elements"]["partial_bandwidth_dl_mu_mimo"] = (
                            (he_phy_info[6] >> 6) & 0x01)
                        output["elements"]["ppe_thresholds_present"] = (
                            (he_phy_info[6] >> 7) & 0x01)

                        output["elements"]["psr_based_sr_support"] = (
                            (he_phy_info[7]) & 0x01)
                        output["elements"]["power_boost_factor_ar_support"] = (
                            (he_phy_info[7] >> 1) & 0x01)
                        output["elements"]["he_su_ppdu_and_he_mu_ppdu_with_4x_he_ltf_and_0.8us_gi"] = (
                            (he_phy_info[7] >> 2) & 0x01)
                        output["elements"]["max_nc"] = (
                            (he_phy_info[7] >> 3) & 0x07)
                        output["elements"]["stbc_tx_>_80mhz"] = (
                            (he_phy_info[7] >> 6) & 0x01)
                        output["elements"]["stbc_rx_>_80mhz"] = (
                            (he_phy_info[7] >> 7) & 0x01)

                        output["elements"]["he_er_su_ppdu_with_4x_he_ltf_and_0.8us_gi"] = (
                            (he_phy_info[8]) & 0x01)
                        output["elements"]["20mhz_in_40mhz_he_ppdu_in_2.4ghz_band"] = (
                            (he_phy_info[8] >> 1) & 0x01)
                        output["elements"]["20mhz_in_160_80+80mhz_he_ppdu"] = (
                            (he_phy_info[8] >> 2) & 0x01)
                        output["elements"]["80mhz_in_160_80+80mhz_he_ppdu"] = (
                            (he_phy_info[8] >> 3) & 0x01)
                        output["elements"]["he_er_su_ppdu_with_1x_he_ltf_and_0.8us_gi"] = (
                            (he_phy_info[8] >> 4) & 0x01)
                        output["elements"]["midamble_tx_rx_2x_and_1x_he_ltf"] = (
                            (he_phy_info[8] >> 5) & 0x01)
                        output["elements"]["dcm_max_ru"] = (
                            (he_phy_info[8] >> 6) & 0x03)

                        output["elements"]["longer_than_16_he_sig_b_ofdm_symbols_support"] = (
                            (he_phy_info[9]) & 0x01)
                        output["elements"]["non_triggered_cqi_feedback"] = (
                            (he_phy_info[9] >> 1) & 0x01)
                        output["elements"]["tx_1024_qam_support_<_242_tone_ru_support"] = (
                            (he_phy_info[9] >> 2) & 0x01)
                        output["elements"]["rx_1024_qam_support_<_242_tone_ru_support"] = (
                            (he_phy_info[9] >> 3) & 0x01)
                        output["elements"]["rx_full_bw_su_using_he_mu_ppdu_with_compressed_he_sig_b"] = (
                            (he_phy_info[9] >> 4) & 0x01)
                        output["elements"]["rx_full_bw_su_using_he_mu_ppdu_with_non_compressed_he_sig_b"] = (
                            (he_phy_info[9] >> 5) & 0x01)
                        output["elements"]["nominal_packet_padding"] = (
                            (he_phy_info[9] >> 6) & 0x03)

                        output["elements"]["he_mu_ppdu_with_more_than_one_ru_rx_max_n_he_ltf"] = (
                            (he_phy_info[10]) & 0x01)

                        output["elements"]["supported_rx_mcs_set_<=_80mhz"] = int.from_bytes(
                            byte_data[20:22], byteorder='little')
                        output["elements"]["supported_tx_mcs_set_<=_80mhz"] = int.from_bytes(
                            byte_data[22:24], byteorder='little')
                        if (output["elements"]["channel_width_set"] & 4 > 0):
                            output["elements"]["supported_rx_mcs_set_160mhz"] = int.from_bytes(
                                byte_data[24:26], byteorder='little')
                            output["elements"]["supported_tx_mcs_set_160mhz"] = int.from_bytes(
                                byte_data[26:28], byteorder='little')
                        if (output["elements"]["channel_width_set"] & 8 > 0):
                            output["elements"]["supported_rx_mcs_set_80+80mhz"] = int.from_bytes(
                                byte_data[28:30], byteorder='little')
                            output["elements"]["supported_tx_mcs_set_80+80mhz"] = int.from_bytes(
                                byte_data[30:32], byteorder='little')

                    case 36:
                        # HE Operation
                        output["type"] = "HE Operation"
                        he_operation_info = byte_data[3:6]
                        output["elements"]["default_pe_duration"] = (
                            he_operation_info[0] & 0x07)
                        output["elements"]["twt_required"] = (
                            (he_operation_info[0] >> 3) & 0x01)
                        output["elements"]["txop_dur_rts_thresh"] = (
                            ((he_operation_info[0] >> 4) & 0x0F)
                            + ((he_operation_info[1] & 0x3F) << 4))
                        output["elements"]["vht_info_present"] = (
                            (he_operation_info[1] >> 6) & 0x01)
                        output["elements"]["cohosted_bss"] = (
                            (he_operation_info[1] >> 7) & 0x01)
                        output["elements"]["er_su_disable"] = (
                            he_operation_info[2] & 0x01)
                        output["elements"]["6ghz_info_present"] = (
                            (he_operation_info[2] >> 1) & 0x01)

                        bss_color_info = byte_data[6]
                        output["elements"]["bss_color"] = (
                            bss_color_info & 0x3F)
                        output["elements"]["partial_bss_color"] = (
                            (bss_color_info >> 6) & 0x01)
                        output["elements"]["bss_color_disabled"] = (
                            (bss_color_info >> 7) & 0x01)

                        output["elements"]["basic_mcs_set"] = int.from_bytes(
                            byte_data[7:9], byteorder='little')

                        start_index = 9
                        if (output["elements"]["vht_info_present"]):
                            # Decode VHT info
                            output["elements"]["vht_info"] = {
                                "channel_width": byte_data[start_index],
                                "channel_center_freq_0": byte_data[start_index + 1],
                                "channel_center_freq_1": byte_data[start_index + 2]
                            }
                            start_index += 3

                        if (output["elements"]["cohosted_bss"]):
                            output["elements"]["max_cohosted_bss_indicator"] = byte_data[start_index]
                            start_index += 1

                        if (output["elements"]["6ghz_info_present"]):
                            control = byte_data[start_index + 1]

                            output["elements"]["6ghz_info"] = {
                                "primary_channel": byte_data[start_index],
                                "channel_width": (control & 0x03),
                                "duplicate_beacon": ((control >> 2) & 0x01),
                                "regulatory_info": ((control >> 3) & 0x07),
                                "channel_center_freq_0": byte_data[start_index + 2],
                                "channel_center_freq_1": byte_data[start_index + 3],
                                "min_rate": byte_data[start_index + 4],
                            }
                            start_index += 5
                    case _:
                        pass
            case _:
                pass
    except Exception as e:
        logging.error(f"Error parsing IE {ie_hex_string} !\n{e}", exc_info=1)

    return output


def process_link(result):
    # Get connected BSSID and bitrate
    bssid = ""
    tx_bitrate = ""
    rx_bitrate = ""
    if (result):
        re_connected = re.compile(
            r"Connected to *([\da-f]{2}:[\da-f]{2}:[\da-f]{2}:[\da-f]{2}:[\da-f]{2}:[\da-f]{2})")
        matches = re_connected.findall(result)
        if (len(matches) > 0):
            bssid = matches[0].upper()
        matches = re_tx_bitrate.findall(result)
        if (len(matches) > 0):
            tx_bitrate = matches[0]
        matches = re_rx_bitrate.findall(result)
        if (len(matches) > 0):
            rx_bitrate = matches[0]

    return {
        "bssid": bssid,
        "tx_bitrate": tx_bitrate,
        "rx_bitrate": rx_bitrate,
    }


def process_link_results(results):
    # Get timestamps and bitrates
    timestamps = re_timestamp.findall(results)
    rssis = re_link_rssi.findall(results)
    tx_bitrates = re_tx_bitrate.findall(results)
    rx_bitrates = re_rx_bitrate.findall(results)

    out_arr = []
    for i in range(0, len(rx_bitrates)):
        out_arr.append({
            "timestamp": timestamps[i].replace(",", "."),
            "rssi": rssis[i],
            "tx_bitrate": tx_bitrates[i],
            "rx_bitrate": rx_bitrates[i]
        })

    return out_arr


def process_scan_results(results, wifi_link):
    # Process Wi-Fi scan results
    results = re_sub.sub(" ", results).split("Cell")
    cells = []
    for entry in results:
        cell = {
            "bssid": "",
            "channel": "",
            "freq": "",
            "rssi": "",
            "ssid": "",
            "connected": False,
            "rates": [],
            "tx_bitrate": "",
            "rx_bitrate": "",
            "extras": []
        }

        for key in re_patterns:
            matches = re_patterns[key].findall(entry)
            if (len(matches) > 0):
                if key == "extras":
                    for ie_hex in matches:
                        # Convert hex string to information element dict
                        ie = read_beacon_ie(ie_hex)
                        cell[key].append(ie)
                elif key == "rates":
                    cell[key] = matches
                else:
                    cell[key] = matches[0]

        if cell["bssid"] != "":
            if cell["bssid"] == wifi_link["bssid"]:
                cell["connected"] = True
                cell["tx_bitrate"] = wifi_link["tx_bitrate"]
                cell["rx_bitrate"] = wifi_link["rx_bitrate"]
            cells.append(cell)

    return cells


def scan(iface="wlan0"):
    # Scan Wi-Fi beacons
    results = utils.run_cmd(
        "sudo iwlist {} scanning".format(iface),
        "Scanning Wi-Fi beacons",
        log_result=False)

    # Get Wi-Fi link
    result_conn = utils.run_cmd(
        "sudo iw dev {} link".format(iface),
        "Get connected Wi-Fi")

    return process_scan_results(results, process_link(result_conn))


def scan_async(iface, link_wait):
    # Start scanning asynchronously
    # Run "iw dev link" after sleeping to capture connected state at perf test
    return {
        "scan": utils.run_cmd_async(
            "sudo iwlist {} scanning".format(iface),
            "Scanning Wi-Fi beacons asynchronously"),
        "link": utils.run_cmd_async(
            "sleep {}; sudo iw dev {} link".format(link_wait, iface),
            "Get connected Wi-Fi link")
    }


def resolve_scan_async(proc_obj):
    results = utils.resolve_cmd_async(
        proc_obj["scan"],
        "Resolving Wi-Fi beacon scan",
        log_result=False)
    result_conn = utils.resolve_cmd_async(
        proc_obj["link"],
        "Resolving Wi-Fi link",
        log_result=False)

    return process_scan_results(results, process_link(result_conn))


def link_async(iface):
    # Continuouly run "iw dev link" to capture Wi-Fi link's bitrates
    return utils.run_cmd_async(
        "while true; do date -Ins; sudo iw dev {} link; done".format(iface),
        "Continuouly get Wi-Fi link")


def resolve_link_async(proc):
    results = utils.resolve_cmd_async(
        proc,
        "Resolving repeated Wi-Fi link call",
        log_result=False,
        kill=True)

    return process_link_results(results)


if __name__ == '__main__':
    print(scan())
