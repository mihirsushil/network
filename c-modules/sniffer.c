/*
 * sniffer.c — low-level packet capture using libpcap
 *
 * Complements analyzer.py by capturing packets at the C level, giving
 * sub-millisecond timing precision.  In a KIOXIA test environment this
 * approach is used to measure exact I/O completion times on a storage
 * bus, where the Python GIL would introduce timing jitter unacceptable
 * for nanosecond-precision SSD latency measurements.
 *
 * Build:   make          (see Makefile)
 * Usage:   sudo ./sniffer [interface] [count]
 *          e.g.  sudo ./sniffer en0 200
 *
 * Output:  JSON to stdout — can be piped directly into the Flask backend
 *          or redirected to a file for offline analysis.
 *
 * Requires: libpcap  (brew install libpcap  /  apt install libpcap-dev)
 */

#include <pcap.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <arpa/inet.h>
#include <netinet/ip.h>
#include <netinet/tcp.h>
#include <netinet/udp.h>
#include <netinet/ip_icmp.h>

/* ── Running totals updated by the pcap callback ───────────────────────────── */
static int g_total = 0;
static int g_tcp   = 0;
static int g_udp   = 0;
static int g_icmp  = 0;
static int g_other = 0;

/* Ethernet header is always 14 bytes — skip it to reach the IP header */
#define ETH_HEADER_LEN 14

/*
 * packet_handler — invoked by libpcap for every captured frame.
 *
 * Kept intentionally minimal: no dynamic allocation, no syscalls inside
 * the callback.  This matches the discipline applied to interrupt handlers
 * in embedded storage controllers — do the least work possible on the
 * hot path and aggregate counts for reporting afterward.
 */
static void packet_handler(u_char        *user_data,
                            const struct pcap_pkthdr *header,
                            const u_char  *packet)
{
    (void)user_data;  /* unused — suppress warning */

    /* Guard against truncated frames shorter than an Ethernet + IP header */
    if (header->caplen < ETH_HEADER_LEN + sizeof(struct ip))
        return;

    const struct ip *ip_hdr = (const struct ip *)(packet + ETH_HEADER_LEN);

    g_total++;

    switch (ip_hdr->ip_p) {
        case IPPROTO_TCP:  g_tcp++;  break;
        case IPPROTO_UDP:  g_udp++;  break;
        case IPPROTO_ICMP: g_icmp++; break;
        default:           g_other++;
    }
}

int main(int argc, char *argv[])
{
    char    errbuf[PCAP_ERRBUF_SIZE];
    pcap_t *handle;

    /* Accept interface and count from the command line; use safe defaults */
    const char *iface = (argc > 1) ? argv[1] : "en0";
    int         count = (argc > 2) ? atoi(argv[2]) : 100;

    if (count <= 0) {
        fprintf(stderr, "[sniffer] count must be a positive integer\n");
        return 1;
    }

    fprintf(stderr, "[sniffer] interface=%s  count=%d\n", iface, count);

    /* Open the interface in promiscuous mode with a 1-second read timeout */
    handle = pcap_open_live(iface, BUFSIZ, /*promisc=*/1, /*timeout_ms=*/1000, errbuf);
    if (handle == NULL) {
        fprintf(stderr, "[sniffer] Could not open %s: %s\n", iface, errbuf);
        fprintf(stderr, "          Try: sudo ./sniffer  or  check the interface name.\n");
        return 1;
    }

    /*
     * BPF filter: capture only IP packets.
     * Filtering in the kernel is far cheaper than filtering in user space —
     * the same principle as using hardware offload for checksum validation
     * rather than doing it in the SSD driver.
     */
    struct bpf_program fp;
    if (pcap_compile(handle, &fp, "ip", /*optimize=*/1, PCAP_NETMASK_UNKNOWN) == -1) {
        fprintf(stderr, "[sniffer] BPF compile failed: %s\n", pcap_geterr(handle));
        pcap_close(handle);
        return 1;
    }
    if (pcap_setfilter(handle, &fp) == -1) {
        fprintf(stderr, "[sniffer] BPF setfilter failed: %s\n", pcap_geterr(handle));
        pcap_freecode(&fp);
        pcap_close(handle);
        return 1;
    }
    pcap_freecode(&fp);

    /* Record start time for throughput calculation */
    time_t start = time(NULL);

    pcap_loop(handle, count, packet_handler, NULL);

    time_t elapsed = time(NULL) - start;
    if (elapsed == 0) elapsed = 1;  /* avoid division by zero */

    pcap_close(handle);

    /*
     * Emit a JSON object to stdout.
     * Using stdout for structured data and stderr for diagnostics follows
     * the UNIX convention and makes it easy to pipe output into other tools
     * — same pattern as NVMe CLI tools that write JSON for scripted test pipelines.
     */
    printf("{\n");
    printf("  \"interface\":     \"%s\",\n",  iface);
    printf("  \"requested\":     %d,\n",      count);
    printf("  \"total_packets\": %d,\n",      g_total);
    printf("  \"TCP\":           %d,\n",      g_tcp);
    printf("  \"UDP\":           %d,\n",      g_udp);
    printf("  \"ICMP\":          %d,\n",      g_icmp);
    printf("  \"Other\":         %d,\n",      g_other);
    printf("  \"elapsed_sec\":   %ld,\n",     (long)elapsed);
    printf("  \"pps\":           %ld\n",      (long)(g_total / elapsed));
    printf("}\n");

    return 0;
}
