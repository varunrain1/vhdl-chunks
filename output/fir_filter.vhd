library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.math_real.all;

entity fir_filter is
  generic (
    DATA_WIDTH : positive := 16;
    COEFF_WIDTH : positive := 16;
    TAPS : positive := 49;
    ACC_WIDTH : positive := 32
  );
  port (
    clk : in std_logic;
    rst : in std_logic;
    ce : in std_logic;
    din : in signed(DATA_WIDTH-1 downto 0);
    dout : out signed(ACC_WIDTH-1 downto 0)
  );
end entity fir_filter;

architecture rtl of fir_filter is

  type coeff_array_t is array (0 to TAPS-1) of signed(COEFF_WIDTH-1 downto 0);
  constant COEFFS : coeff_array_t := (
    to_signed(-5, 16),  -- -0.00030422
    to_signed(-7, 16),  -- -0.00044685
    to_signed(-10, 16),  -- -0.00061293
    to_signed(-13, 16),  -- -0.00080238
    to_signed(-17, 16),  -- -0.00101463
    to_signed(-20, 16),  -- -0.00124860
    to_signed(-25, 16),  -- -0.00150269
    to_signed(-29, 16),  -- -0.00177478
    to_signed(-34, 16),  -- -0.00206227
    to_signed(-39, 16),  -- -0.00236210
    to_signed(-44, 16),  -- -0.00267081
    to_signed(-49, 16),  -- -0.00298458
    to_signed(-54, 16),  -- -0.00329931
    to_signed(-59, 16),  -- -0.00361069
    to_signed(-64, 16),  -- -0.00391431
    to_signed(-69, 16),  -- -0.00420570
    to_signed(-73, 16),  -- -0.00448048
    to_signed(-78, 16),  -- -0.00473441
    to_signed(-81, 16),  -- -0.00496348
    to_signed(-85, 16),  -- -0.00516405
    to_signed(-87, 16),  -- -0.00533286
    to_signed(-90, 16),  -- -0.00546714
    to_signed(-91, 16),  -- -0.00556468
    to_signed(-92, 16),  -- -0.00562387
    to_signed(16295, 16),  -- 0.99459503
    to_signed(-92, 16),  -- -0.00562387
    to_signed(-91, 16),  -- -0.00556468
    to_signed(-90, 16),  -- -0.00546714
    to_signed(-87, 16),  -- -0.00533286
    to_signed(-85, 16),  -- -0.00516405
    to_signed(-81, 16),  -- -0.00496348
    to_signed(-78, 16),  -- -0.00473441
    to_signed(-73, 16),  -- -0.00448048
    to_signed(-69, 16),  -- -0.00420570
    to_signed(-64, 16),  -- -0.00391431
    to_signed(-59, 16),  -- -0.00361069
    to_signed(-54, 16),  -- -0.00329931
    to_signed(-49, 16),  -- -0.00298458
    to_signed(-44, 16),  -- -0.00267081
    to_signed(-39, 16),  -- -0.00236210
    to_signed(-34, 16),  -- -0.00206227
    to_signed(-29, 16),  -- -0.00177478
    to_signed(-25, 16),  -- -0.00150269
    to_signed(-20, 16),  -- -0.00124860
    to_signed(-17, 16),  -- -0.00101463
    to_signed(-13, 16),  -- -0.00080238
    to_signed(-10, 16),  -- -0.00061293
    to_signed(-7, 16),  -- -0.00044685
    to_signed(-5, 16)  -- -0.00030422
  );


  type delay_array is array (0 to TAPS-1) of signed(DATA_WIDTH-1 downto 0);

  signal delay_line : delay_array := (others => (others => '0'));
  signal acc : signed(ACC_WIDTH-1 downto 0) := (others => '0');
begin

  process(clk, rst)
    variable sum : signed(ACC_WIDTH-1 downto 0);
  begin
    if rst = '1' then
      delay_line <= (others => (others => '0'));
      acc        <= (others => '0');
    elsif rising_edge(clk) then
      if ce = '1' then
        -- unit-delay chain
        delay_line(0) <= din;
        for i in 1 to TAPS-1 loop
          delay_line(i) <= delay_line(i-1);
        end loop;

        -- multiply-accumulate
        sum := (others => '0');
        for i in 0 to TAPS-1 loop
          sum := sum + resize(delay_line(i) * COEFFS(i), ACC_WIDTH);
        end loop;
        acc <= sum;
      end if;
    end if;
  end process;
  dout <= acc;

end architecture rtl;