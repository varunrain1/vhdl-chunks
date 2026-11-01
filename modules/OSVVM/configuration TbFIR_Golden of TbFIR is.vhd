configuration TbFIR_Golden of TbFIR is
  for TestHarness
    for TestCtrl_1 : TestCtrl
      use entity work.TestCtrl(Golden);
    end for;
  end for;
end configuration TbFIR_Golden;