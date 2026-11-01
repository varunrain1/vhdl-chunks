# OSVVM Testbench for fir_filter (separate scenarios)

## Layout

- fir_tb_pkg.vhd           types + coefficients (match DUT)
- TestCtrl_fir_utils.vhd   SendSample + RefStep
- TestCtrl_fir.vhd         entity only
- Test_Impulse.vhd         architecture Test_Impulse
- Test_Step.vhd            architecture Test_Step
- Test_Tone.vhd            architecture Test_Tone
- Test_Random.vhd          architecture Test_Random
- StreamSource_VC.vhd      source VC
- StreamSink_VC.vhd        sink VC
- tb_fir_filter.vhd        harness
- tb_fir_configs.vhd       configurations (pick one scenario)

## Run one scenario at a time

| Configuration    | Scenario                        |
|------------------|---------------------------------|
| tb_fir_impulse   | Impulse response                |
| tb_fir_step      | Step response                   |
| tb_fir_tone      | Low-frequency sine (64 samples) |
| tb_fir_random    | 200 constrained-random + coverage |

### Questa / ModelSim

    vcom -2008 fir_filter.vhd
    vcom -2008 fir_tb_pkg.vhd TestCtrl_fir_utils.vhd TestCtrl_fir.vhd
    vcom -2008 Test_Impulse.vhd Test_Step.vhd Test_Tone.vhd Test_Random.vhd
    vcom -2008 StreamSource_VC.vhd StreamSink_VC.vhd
    vcom -2008 tb_fir_filter.vhd tb_fir_configs.vhd

    vsim -c work.tb_fir_impulse
    run -all

    # or: work.tb_fir_step / work.tb_fir_tone / work.tb_fir_random

## Notes

- C_COEFFS in fir_tb_pkg.vhd must match constants in generated fir_filter.vhd
- Reference model: MAC on delay line, then shift din in (same as RTL)
- Each architecture owns its scoreboard and checker process
- Requires OSVVM with OsvvmContext
