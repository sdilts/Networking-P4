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
    def __init__(self, maxsize=0):
        self.in_queue = queue.Queue(maxsize)
        self.out_queue = queue.Queue(maxsize)

    ##get packet from the queue interface
    # @param in_or_out - use 'in' or 'out' interface
    def get(self, in_or_out):
        try:
            if in_or_out == 'in':
                pkt_S = self.in_queue.get(False)
                # if pkt_S is not None:
                #     print('getting packet from the IN queue')
                return pkt_S
            else:
                pkt_S = self.out_queue.get(False)
                # if pkt_S is not None:
                #     print('getting packet from the OUT queue')
                return pkt_S
        except queue.Empty:
            return None

    ##put the packet into the interface queue
    # @param pkt - Packet to be inserted into the queue
    # @param in_or_out - use 'in' or 'out' interface
    # @param block - if True, block until room in queue, if False may throw queue.Full exception
    def put(self, pkt, in_or_out, block=False):
        if in_or_out == 'out':
            # print('putting packet in the OUT queue')
            self.out_queue.put(pkt, block)
        else:
            # print('putting packet in the IN queue')
            self.in_queue.put(pkt, block)


## Implements a network layer packet.
class NetworkPacket:
    ## packet encoding lengths
    dst_S_length = 5
    prot_S_length = 1

    ##@param dst: address of the destination host
    # @param data_S: packet payload
    # @param prot_S: upper layer protocol for the packet (data, or control)
    def __init__(self, dst, prot_S, data_S):
        self.dst = dst
        self.data_S = data_S
        self.prot_S = prot_S

    ## called when printing the object
    def __str__(self):
        return self.to_byte_S()

    ## convert packet to a byte string for transmission over links
    def to_byte_S(self):
        byte_S = str(self.dst).zfill(self.dst_S_length)
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
        dst = byte_S[0 : NetworkPacket.dst_S_length].strip('0')
        prot_S = byte_S[NetworkPacket.dst_S_length : NetworkPacket.dst_S_length + NetworkPacket.prot_S_length]
        if prot_S == '1':
            prot_S = 'data'
        elif prot_S == '2':
            prot_S = 'control'
        else:
            raise('%s: unknown prot_S field: %s' %(self, prot_S))
        data_S = byte_S[NetworkPacket.dst_S_length + NetworkPacket.prot_S_length : ]
        return self(dst, prot_S, data_S)




## Implements a network host for receiving and transmitting data
class Host:

    ##@param addr: address of this node represented as an integer
    def __init__(self, addr):
        self.addr = addr
        self.intf_L = [Interface()]
        self.stop = False #for thread termination

    ## called when printing the object
    def __str__(self):
        return self.addr

    ## create a packet and enqueue for transmission
    # @param dst: destination address for the packet
    # @param data_S: data being transmitted to the network layer
    def udt_send(self, dst, data_S):
        p = NetworkPacket(dst, 'data', data_S)
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



## Implements a multi-interface router
class Router:

    ##@param name: friendly router name for debugging
    # @param cost_D: cost table to neighbors {neighbor: {interface: cost}}
    # @param max_queue_size: max queue length (passed to Interface)
    def __init__(self, name, cost_D, max_queue_size):
        self.stop = False #for thread termination
        self.name = name
        #create a list of interfaces
        self.intf_L = [Interface(max_queue_size) for _ in range(len(cost_D))]
        print()
        #save neighbors and interfeces on which we connect to them
        self.cost_D = cost_D    # {neighbor: {interface: cost}}
        #TODO: set up the routing table for connected hosts
        self.rt_tbl_D = {}      # {destination: {router: cost}}
        self.init_table()
        print('%s: Initialized routing table' % self)
        self.print_routes()


    ## called when printing the object
    def __str__(self):
        return self.name

    def init_table(self):
        for neighb, cost in self.cost_D.items():
            for key, val in cost.items():
                self.rt_tbl_D.update({neighb:{self.name:val}})
        print(self.rt_tbl_D)


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
            # for now we assume the outgoing interface is 1
            self.intf_L[1].put(p.to_byte_S(), 'out', True)
            print('%s: forwarding packet "%s" from interface %d to %d' % \
                (self, p, i, 1))
        except queue.Full:
            print('%s: packet "%s" lost on interface %d' % (self, p, i))
            pass


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


    ## forward the packet according to the routing table
    #  @param p Packet containing routing information
    def update_routes(self, p: RouterMessage, i):
        #TODO: add logic to update the routing tables and
        # possibly send out routing updates
        print('%s: Received routing update %s from interface %d' % (self, p, i))
        change = False
        for host, router in p.table.items():
            for r, cost in router.items():
                if r != self.name:
                    if host in self.rt_tbl_D.keys():
                        #print(i, " i ", r, " r ", host, " host ", cost, " cost ")
                        new_cost = p.table[host][r] + self.rt_tbl_D[r][self.name]
                        if r in self.rt_tbl_D[host].keys():
                            old_cost = self.rt_tbl_D[host][r]
                        else:
                            old_cost = float("inf")
                        print("new cost: ", new_cost, "   old cost: ", old_cost, "   host: ", host, "   router: ", r)
                        if new_cost < old_cost and r == self.name:
                            self.rt_tbl_D[host][r] = new_cost
                            change = True

                    else:
                        print("router ",router)
                        self.rt_tbl_D.update({host:router})
                        change = True
                # else:
                #     self.rt_tbl_D[host][r
        if change:
            self.fix_table()
            print("I'm a teapot")
            self.print_routes()
            self.send_routes(i)

    def fix_table(self):
        notMe = ''
        for host, router in self.rt_tbl_D.items():
            copy = dict(router)
            for r, cost in copy.items():
                if r != self.name and self.name != host:
                    last_cost = cost + self.rt_tbl_D[r][self.name]
                    notMe = r
                    x = self.find_fastest_route(host)
                    # if last_cost <= x[1]:
                    self.rt_tbl_D[host][self.name] = last_cost

        # for host, router in self.rt_tbl_D.items():
        #     copy = dict(router)
        #     for r, cost in copy.items():
        #         if r == self.name and notMe != host:
        #             last_cost = cost + self.rt_tbl_D[r][notMe]

        #             x = self.find_fastest_route(host)
        #             if last_cost <= x[1]:
        #                 self.rt_tbl_D[host][notMe] = last_cost


    def find_fastest_route(self, host):
        fast = 10000
        fast_inter = None
        for router in self.rt_tbl_D[host].keys():
            if self.rt_tbl_D[host][router] < fast:
                fast = self.rt_tbl_D[host][router]
                fast_inter = router

        return fast_inter, fast


    def build_update_tbl(self):
        tbl = dict()
        # for host, router in self.rt_tbl_D.items():
        #     for r, cost in router.items():
        #         tbl.update({host:{r:self.find_fastest_route(host)[1]}})
        #         #tbl[host][r] = self.find_fastest_route(host)[1]
        # return tbl
        return self.rt_tbl_D


    print_lock = threading.Lock()
    ## Print routing table
    def print_routes(self):
        self.print_lock.acquire()
        print('%s: routing table' % self)
        #TODO: print the routes as a two dimensional table for easy inspection
        # Currently the function just prints the route table as a dictionary
        print(self.rt_tbl_D)
        print("       Cost to:")
        print("    ",self.name," ", end='')
        # print all possible keys for the hosts:
        names = ['H1', 'H2', 'RA', 'RB']
        routers = ['RA', 'RB']
        for name in names:

            print(name + " ", end='')
        print()
        for index, router in enumerate(routers):
            if index == 0:
                print("From ", end='')
            else:
                print("     ", end='')
            print(router + "  ", end='')
            for name in names:
                if name in self.rt_tbl_D.keys():
                    if router in self.rt_tbl_D[name].keys():
                        print(str(self.rt_tbl_D[name][router]) + "  ",end='')
                    else:
                        print("-  ", end='')
                else:
                    print("-  ", end='')
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


    ## thread target for the host to keep forwarding data
    def run(self):
        print (threading.currentThread().getName() + ': Starting')
        while True:
            self.process_queues()
            if self.stop:
                print (threading.currentThread().getName() + ': Ending')
                return
