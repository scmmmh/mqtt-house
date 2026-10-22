from pimoroni_yukon import SLOT1, SLOT5, Yukon
from pimoroni_yukon.modules import BigMotorModule, RM2WirelessModule

from mqtt_house.device.generic import Device

GEAR_RATIO = 50  # The gear ratio of the motor
ENCODER_CPR = 12  # The number of counts a single encoder shaft revolution will produce
MOTOR_CPR = GEAR_RATIO * ENCODER_CPR  # The number of counts a single motor shaft revolution will produce
ENCODER_PIO = 0  # The PIO system to use (0 or 1) for the motor's encoder
ENCODER_SM = 0  # The State Machines (SM) to use for the motor's encoder

class YukonDevice(Device):
    async def start(self):
        """Start the controller."""
        yukon = Yukon()
        module = RM2WirelessModule()
        yukon.register_with_slot(module, SLOT5)
        module = BigMotorModule(encoder_pio=ENCODER_PIO, encoder_sm=ENCODER_SM, counts_per_rev=MOTOR_CPR)
        yukon.register_with_slot(module, SLOT1)
        yukon.verify_and_initialise()
        yukon.enable_main_output()
