#!/usr/bin/python
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node, OVSController, OVSKernelSwitch
from mininet.log import setLogLevel, info
from mininet.cli import CLI


class LinuxRouter(Node):
    "A Node with IP forwarding enabled."

    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        # Enable forwarding on the router
        self.cmd('sysctl net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()


class NetworkTopo(Topo):
    def build(self, **_opts):
        # Create 4 routers
        router1 = self.addNode('r1', cls=LinuxRouter)
        router2 = self.addNode('r2', cls=LinuxRouter)
        router3 = self.addNode('r3', cls=LinuxRouter)
        router4 = self.addNode('r4', cls=LinuxRouter)

        # Create a list of routers
        routers = [router1, router2, router3, router4]

	#Add switches if needed (your code includes a switch s5 connected to routers)
        s5 = self.addSwitch('s5', cls=OVSKernelSwitch)
        self.addLink(s5, router1, intfName2='r1-eth0', params2={'ip': '192.168.3.1/29'})
        self.addLink(s5, router2, intfName2='r2-eth0', params2={'ip': '192.168.3.2/29'})
        self.addLink(s5, router3, intfName2='r3-eth0', params2={'ip': '192.168.3.3/29'})
        self.addLink(s5, router4, intfName2='r4-eth0', params2={'ip': '192.168.3.4/29'})


from time import sleep
def run():
    topo = NetworkTopo()
    net = Mininet(topo=topo, switch=OVSKernelSwitch, controller=OVSController)
    net.start()

    routers = ['r1', 'r2', 'r3', 'r4']
    # Set up ip-addresses
    net['r1'].cmd('ifconfig r1-eth0 192.168.3.1 netmask 255.255.255.248 up')
    net['r2'].cmd('ifconfig r2-eth0 192.168.3.2 netmask 255.255.255.248 up')
    net['r3'].cmd('ifconfig r3-eth0 192.168.3.3 netmask 255.255.255.248 up')
    net['r4'].cmd('ifconfig r4-eth0 192.168.3.4 netmask 255.255.255.248 up')
    
    # Disable offloading features (optional but good for certain routing tests)
    for r in routers:
         intf = f'{r}-eth0'
         net[r].cmd(f'/sbin/ethtool -K {intf} rx off tx off sg off')
         net[r].cmd(f'ifconfig {intf} mtu 9000' )

    # You can check routing tables here if needed
    for r in routers:
        info(f'*** Routing Table on {r}:\n')
        info(net[r].cmd('route -n'))





    router_dirs = {
    'r1': 'router1',
    'r2': 'router2',
    'r3': 'router3',
    'r4': 'router4'
    }

    for r in routers:
        dir_name = router_dirs[r]
        info(f'*** Starting HIPLS on {r} ({dir_name}/switchd.py) ***\n')
        net[r].cmd(f'cd {dir_name} && python3 switchd.py > switchd.log 2>&1 &')
    # Start HIPLS daemon on each router
    #for r in routers:
    #    info(f'*** Starting HIPLS on {r} ***\n')
        #net[r].cmd(f'cd {r} && python3 switchd.py &')
    #    net[r].cmd(f'cd {r} && python3 switchd.py > switchd.log 2>&1 &')

    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
