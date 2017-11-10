'''
Created on Oct 12, 2016

@author: mwitt_000
'''
import queue
import threading
import ast

class RouterMessage:
    tbl_len = 30
    name_length = 5

    def __init__(self, router_name, table):
        self.table = table
        self.router_name = router_name

    def to_byte_S(self):
        # fancy stuff:
        byte_S = str(self.router_name).zfill(self.name_length)
        byte_S += str(self.table).zfill(self.tbl_len)
        return byte_S

    @classmethod
    def from_byte_S(self, byte_S):
        router_name = byte_S[:self.name_length]
        table = byte_S[self.name_length:]
        table = ast.literal_eval(table.strip('0'))
        return self(router_name, table)




## wrapper class for a queue of packets
class Interface:
    ## @param maxsize - the maximum size of the queue storing packets
    #  @param cost - of the interface used in routing
    def __init__(self, cost=0, maxsize=0):
        self.in_queue = queue.Queue(maxsize);
        self.out_queue = queue.Queue(maxsize);
        self.cost = cost

    ##get packet from the queue interface
    # @param in_or_out - use 'in' or 'out' interface
    def get(self, in_or_out):
        try:
            if in_or_out == 'in':
                pkt_S = self.in_queue.get(False)
#                 if pkt_S is not None:
#                     print('getting packet from the IN queue')
                return pkt_S
            else:
                pkt_S = self.out_queue.get(False)
#                 if pkt_S is not None:
#                     print('getting packet from the OUT queue')
                return pkt_S
        except queue.Empty:
            return None

    ##put the packet into the interface queue
    # @param pkt - Packet to be inserted into the queue
    # @param in_or_out - use 'in' or 'out' interface
    # @param block - if True, block until room in queue, if False may throw queue.Full exception
    def put(self, pkt, in_or_out, block=False):
        if in_or_out == 'out':
#             print('putting packet in the OUT queue')
            self.out_queue.put(pkt, block)
        else:
#             print('putting packet in the IN queue')
            self.in_queue.put(pkt, block)


## Implements a network layer packet (different from the RDT packet
# from programming assignment 2).
# NOTE: This class will need to be extended to for the packet to include
# the fields necessary for the completion of this assignment.
class NetworkPacket:
    ## packet encoding lengths
    dst_addr_S_length = 5
    prot_S_length = 1

    ##@param dst_addr: address of the destination host
    # @param data_S: packet payload
    # @param prot_S: upper layer protocol for the packet (data, or control)
    def __init__(self, dst_addr, prot_S, data_S):
        self.dst_addr = dst_addr
        self.data_S = data_S
        self.prot_S = prot_S

    ## called when printing the object
    def __str__(self):
        return self.to_byte_S()

    ## convert packet to a byte string for transmission over links
    def to_byte_S(self):
        byte_S = str(self.dst_addr).zfill(self.dst_addr_S_length)
        if self.prot_S == 'data':
            byte_S += '1'
        elif self.prot_S == 'control':
            byte_S += '2'
        else:
            raise('%s: unknown prot_S option: %s' %(self, self.prot_S))
        byte_S += self.data_S
        return byte_S

    ## extract a packet object from a byte string
    # @param byte_S: byte string representation of the packet
    @classmethod
    def from_byte_S(self, byte_S):
        dst_addr = int(byte_S[0 : NetworkPacket.dst_addr_S_length])
        prot_S = byte_S[NetworkPacket.dst_addr_S_length : NetworkPacket.dst_addr_S_length + NetworkPacket.prot_S_length]
        if prot_S == '1':
            prot_S = 'data'
        elif prot_S == '2':
            prot_S = 'control'
        else:
            raise('%s: unknown prot_S field: %s' %(self, prot_S))
        data_S = byte_S[NetworkPacket.dst_addr_S_length + NetworkPacket.prot_S_length : ]
        return self(dst_addr, prot_S, data_S)




## Implements a network host for receiving and transmitting data
class Host:

    ##@param addr: address of this node represented as an integer
    def __init__(self, addr):
        self.addr = addr
        self.intf_L = [Interface()]
        self.stop = False #for thread termination

    ## called when printing the object
    def __str__(self):
        return 'Host_%s' % (self.addr)

    ## create a packet and enqueue for transmission
    # @param dst_addr: destination address for the packet
    # @param data_S: data being transmitted to the network layer
    def udt_send(self, dst_addr, data_S):
        p = NetworkPacket(dst_addr, 'data', data_S)
        print('%s: sending packet "%s"' % (self, p))
        self.intf_L[0].put(p.to_byte_S(), 'out') #send packets always enqueued successfully

    ## receive packet from the network layer
    def udt_receive(self):
        pkt_S = self.intf_L[0].get('in')
        if pkt_S is not None:
            print('%s: received packet "%s"' % (self, pkt_S))

    ## thread target for the host to keep receiving data
    def run(self):
        print (threading.currentThread().getName() + ': Starting')
        while True:
            #receive data arriving to the in interface
            self.udt_receive()
            #terminate
            if(self.stop):
                print (threading.currentThread().getName() + ': Ending')
                return



## Implements a multi-interface router described in class
class Router:

    ##@param name: friendly router name for debugging
    # @param intf_cost_L: outgoing cost of interfaces (and interface number)
    # @param rt_tbl_D: routing table dictionary (starting reachability), eg. {1: {1: 1}} # packet to host 1 through interface 1 for cost 1
    # @param max_queue_size: max queue length (passed to Interface)
    def __init__(self, name, intf_cost_L, rt_tbl_D, max_queue_size):
        self.stop = False #for thread termination
        self.name = name
        #create a list of interfaces
        #note the number of interfaces is set up by out_intf_cost_L
        self.intf_L = []
        for cost in intf_cost_L:
            self.intf_L.append(Interface(cost, max_queue_size))
        #set up the routing table for connected hosts
        self.rt_tbl_D = rt_tbl_D

    ## called when printing the object
    def __str__(self):
        return 'Router_%s' % (self.name)

    ## look through the content of incoming interfaces and
    # process data and control packets
    def process_queues(self):
        for i in range(len(self.intf_L)):
            pkt_S = None
            #get packet from interface i
            pkt_S = self.intf_L[i].get('in')
            #if packet exists make a forwarding decision
            if pkt_S is not None:
                p = NetworkPacket.from_byte_S(pkt_S) #parse a packet out
                if p.prot_S == 'data':
                    self.forward_packet(p,i)
                elif p.prot_S == 'control':
                    mssg = RouterMessage.from_byte_S(p.data_S)
                    self.update_routes(mssg, i)
                else:
                    raise Exception('%s: Unknown packet type in packet %s' % (self, p))

    ## forward the packet according to the routing table
    #  @param p Packet to forward
    #  @param i Incoming interface number for packet p
    def forward_packet(self, p, i):
        try:
            # TODO: Here you will need to implement a lookup into the
            # forwarding table to find the appropriate outgoing interface
            # for now we assume the outgoing interface is (i+1)%2
            interface = self.find_fastest_route(p.dst_addr)[0]
            self.intf_L[interface].put(p.to_byte_S(), 'out', True)
            print('%s: forwarding packet "%s" from interface %d to %d' % (self, p, i, interface))
        except queue.Full:
            print('%s: packet "%s" lost on interface %d' % (self, p, i))
            pass

    ## forward the packet according to the routing table
    #  @param p Packet containing routing information
    def update_routes(self, p: RouterMessage, i):
        #TODO: add logic to update the routing tables and
        # possibly send out routing updates
        print('%s: Received routing update %s from interface %d' % (self, p, i))
        change = False
        for host in p.table.keys():
            if host in self.rt_tbl_D.keys():
                # compute the new cost to get to the host:
                new_cost = self.intf_L[i].cost + p.table[host]
                old_cost = self.find_fastest_route(host)
                if new_cost < old_cost[1]:
                    self.rt_tbl_D[host][i] = new_cost
                    change = True
            else:
                self.rt_tbl_D[host] = dict()
                self.rt_tbl_D[host][i] = self.intf_L[i].cost + p.table[host]
                change = True
        if change:
            print("I'm a teapot")
            self.print_routes()
            self.send_routes(i)


    def find_fastest_route(self, host):
        fast = 10000
        fast_inter = None
        for interface in self.rt_tbl_D[host].keys():
            if self.rt_tbl_D[host][interface] < fast:
                fast = self.rt_tbl_D[host][interface]
                fast_inter = interface

        return fast_inter, fast

    def build_update_tbl(self):
        tbl = dict()
        for host in self.rt_tbl_D.keys():
            tbl[host] = self.find_fastest_route(host)[1]
        return tbl

    ## send out route update
    # @param i Interface number on which to send out a routing update
    def send_routes(self, i):
        # construct the interface table:
        # a sample route update packet
        p = NetworkPacket(0, 'control',  RouterMessage(self.name, self.build_update_tbl() ).to_byte_S())
        try:
            #TODO: add logic to send out a route update
            print('%s: sending routing update "%s" from interface %d' % (self, p, i))
            self.intf_L[i].put(p.to_byte_S(), 'out', True)
        except queue.Full:
            print('%s: packet "%s" lost on interface %d' % (self, p, i))
            pass

    print_lock = threading.Lock()
    ## Print routing table
    def print_routes(self):
        self.print_lock.acquire()
        print('%s: routing table' % self)
        #TODO: print the routes as a two dimensional table for easy inspection
        # Currently the function just prints the route table as a dictionary
        print(self.rt_tbl_D)
        print("       Cost to:")
        print("        ", end='')
        # print all possible keys for the hosts:
        for i in range(1,3):
            print(str(i) + " ", end='')
        print()
        for inter in range(len(self.intf_L)):

            if inter == 0:
                print("From ", end='')
            else:
                print("     ", end='')
            print(str(inter) + "  ", end='')
            for host in range(1,3):
                if host in self.rt_tbl_D.keys():
                    if inter in self.rt_tbl_D[host].keys():
                        print(str(self.rt_tbl_D[host][inter]) + " ",end='')
                    else:
                        print("- ", end='')
                else:
                    print("- ", end='')
            print()
        print()
        self.print_lock.release()

        # print the keys:
        # for i in self.rt_tbl_D.keys():
        #     print(i,end='')
        # print()
        # for i in self.rt_tbl_D.keys():
        #     print("    ", end='')
        #     print(self.rt_tbl_D[i][0], end='')
        #     for val in self.rt_tbl_D[i].keys():
        #         print(" " + str(self.rt_tbl_D[i][val]), end='')
        #     print()



        print()

    def init_table(self):
        for interface in range(len(self.intf_L)):
            self.send_routes(interface)



    ## thread target for the host to keep forwarding data
    def run(self):

        print (threading.currentThread().getName() + ': Starting')
        self.init_table()
        while True:
            self.process_queues()
            if self.stop:
                print (threading.currentThread().getName() + ': Ending')
                return
