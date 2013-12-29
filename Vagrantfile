# require: vagrant plugin install vagrant-hosts
# require: vagrant plugin install vagrant-hostsupdater

domain = 'loc'
ip_prefix = '192.168.1.'

nodes = [
  { :hostname => 'nas', :ip => '33' },
]
 
Vagrant.configure("2") do |config|
    nodes.each do |node|
 
        config.vm.define node[:hostname] do |node_config|
            node_config.vm.box = node[:box] ? node[:box] : 'precise32'
            node_config.vm.host_name = node[:hostname] + '.' + domain
            node_config.vm.network :private_network, :ip => ip_prefix + node[:ip]

            node_config.vm.provider :virtualbox do |vb|
                memory = node[:ram] ? node[:ram] : 256
                vb.customize [
                    'modifyvm', :id,
                    '--name', node[:hostname],
                    '--memory', memory.to_s
                ]
                vb.gui = node[:ui]
            end

        end
    end
    config.vm.provision :hosts
end
