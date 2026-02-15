import pyvisa as visa
import re

rm = visa.ResourceManager()
resources = rm.list_resources()
print(resources)
matching_resources = [match for match in resources if re.search(r'GPIB.*INSTR$',match)]
print(matching_resources)
inst = rm.open_resource(matching_resources[0])

inst.write('*FA?')

print(inst.read())

# inst.write('FR 24 GZ')

inst.write('*FA?')

print(inst.read())


inst.close()