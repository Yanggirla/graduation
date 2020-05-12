from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet,tcp,udp,ipv4
from ryu.lib.packet import ether_types


class Tcp_Udp_Path_Choose(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(Tcp_Udp_Path_Choose, self).__init__(*args, **kwargs)
        self.mac_to_port = {}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        ips = pkt.get_protocol(ipv4.ipv4)
        udps = pkt.get_protocol(udp.udp)
        tcps = pkt.get_protocol(tcp.tcp)

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return
        eth_dst = eth.dst
        eth_src = eth.src

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        self.mac_to_port[dpid][eth_src] = in_port

        if ips!=None:
            # tcp path choose
            if tcps!=None:
		# ��������ֶ��Ļ�����Ҫʵ�ֶ˿ڷ��ֻ��ƣ����Ⱥ�����Ϳ���ֱ�ӵķ���
		# �� output = dpid_port[1][src]
		#    back_port = dpid_port[1][dst]   ���src��dts����s1��s2���ӵ���·�����ˡ�
                if dpid == 1:
                    # �����s1����s2 s1_1-s2_1�������Ҫ�������Լ�������������
                    out_port = 1
                    back_port = 1
                elif dpid == 2:
                    # �����s2����s4 s2_2-s4_1
                    out_port = 2
                    back_port = 1
            elif udps !=None:
                if dpid == 1:
                    # �����s1����s3 s1_2-s3_1
                    out_port = 2
                    back_port = 1
                elif dpid == 3:
                    # �����s3����s4 s3_2-s4_2
                    out_port = 2
                    back_port = 2
            else:
                out_port = self.mac_to_port[dpid][eth_dst]
        elif eth_dst in self.mac_to_port[dpid]:  # no ip packets
            out_port = self.mac_to_port[dpid][eth_dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD:
            # start to add match
            if tcps!=None:
                # ����tcp�ķ��صĶ���
                back_action = [parser.OFPActionOutput(back_port)]
                # ����tcp��ȥ�Ĳ���
                tcp_match_go = parser.OFPMatch(in_port=in_port, eth_dst=eth_dst, eth_src=eth_src, ethertype=ethernet.ether.ETH_TYPE_IP,
                                src=ips.src, dst=ips.dst, proto=ipv4.inet.IPPROTO_TCP)
                # ����tcp�ķ���ʱ�Ĳ���
                tcp_match_back = parser.OFPMatch(in_port=in_port, eth_src=eth_dst, eth_dst=eth_src, ethertype=ethernet.ether.ETH_TYPE_IP,
                                dst=ips.src, src=ips.dst, proto=ipv4.inet.IPPROTO_TCP)
                # �������
                self.add_flow(datapath, 1, tcp_match_go, actions)
                self.add_flow(datapath, 1, tcp_match_back, back_action)
                # ��������ǰ����˶˿ںŵ�tcp�������
                # parser.OFPMatch(in_port=in_port, eth_dst=eth_dst, eth_src=eth_src,ethertype = ethernet.ether.ETH_TYPE_IP,
                #                src = ips.src,dst = ips.dst,proto =ipv4.inet.IPPROTO_TCP,,src_port=tcps.src_port,dst__port=tcps.dst_port)

            elif udps!=None:
                back_action = [parser.OFPActionOutput(back_port)]
                tcp_match_go = parser.OFPMatch(in_port=in_port, eth_dst=eth_dst, eth_src=eth_src, ethertype=ethernet.ether.ETH_TYPE_IP,
                                src=ips.src, dst=ips.dst, proto=ipv4.inet.IPPROTO_UDP)
                tcp_match_back = parser.OFPMatch(in_port=in_port, eth_src=eth_dst, eth_dst=eth_src,
                                                 ethertype=ethernet.ether.ETH_TYPE_IP,
                                                 dst=ips.src, src=ips.dst, proto=ipv4.inet.IPPROTO_UDP)
                # ��������ǰ����˶˿ںŵ�udp�������
                # parser.OFPMatch(in_port=in_port, eth_dst=eth_dst, eth_src=eth_src,ethertype = ethernet.ether.ETH_TYPE_IP,
                #                src = ips.src,dst = ips.dst,proto =ipv4.inet.IPPROTO_TCP,,src_port=udps.src_port,dst__port=udps.dst_port)
                self.add_flow(datapath, 1, tcp_match_go, actions)
                self.add_flow(datapath, 1, tcp_match_back, back_action)
            else:
                match = parser.OFPMatch(in_port=in_port, eth_dst=eth_dst, eth_src=eth_src)
                self.add_flow(datapath, 1, match, actions)

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)


