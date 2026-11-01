--------------------------------------------------------------------------------
-- tb_fir_configs.vhd
-- Select which scenario architecture binds to TestCtrl_fir in the harness.
--
-- Simulate one of:
--   tb_fir_impulse
--   tb_fir_step
--   tb_fir_tone
--   tb_fir_random
--------------------------------------------------------------------------------

configuration tb_fir_impulse of tb_fir_filter is
  for test_harness
    for u_ctrl : TestCtrl_fir
      use entity work.TestCtrl_fir(Test_Impulse);
    end for;
  end for;
end configuration tb_fir_impulse;

configuration tb_fir_step of tb_fir_filter is
  for test_harness
    for u_ctrl : TestCtrl_fir
      use entity work.TestCtrl_fir(Test_Step);
    end for;
  end for;
end configuration tb_fir_step;

configuration tb_fir_tone of tb_fir_filter is
  for test_harness
    for u_ctrl : TestCtrl_fir
      use entity work.TestCtrl_fir(Test_Tone);
    end for;
  end for;
end configuration tb_fir_tone;

configuration tb_fir_random of tb_fir_filter is
  for test_harness
    for u_ctrl : TestCtrl_fir
      use entity work.TestCtrl_fir(Test_Random);
    end for;
  end for;
end configuration tb_fir_random;
