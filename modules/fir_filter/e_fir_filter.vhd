library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.math_real.all;

entity e_fir_filter is
  generic (
    g_DATA_WIDTH : positive := 16;
    g_COEFF_WIDTH : positive := 16;
    g_TAPS : positive := 16;
    g_ACC_WIDTH : positive := 32
  );
  port (
    i_clk : in std_logic;
    i_rst : in std_logic;
    i_ce : in std_logic;
    i_din : in signed(g_DATA_WIDTH-1 downto 0);
    o_dout : out signed(g_ACC_WIDTH-1 downto 0)
  );
end entity e_fir_filter;

architecture rtl of e_fir_filter is

  type coeff_array_t is array (0 to g_TAPS-1) of signed(g_COEFF_WIDTH-1 downto 0);
  constant c_COEFFS : coeff_array_t := (
    to_signed(0, 16),  -- 0.00000000
    to_signed(183, 16),  -- 0.00557150
    to_signed(259, 16),  -- 0.00788956
    to_signed(-541, 16),  -- -0.01652200
    to_signed(-1665, 16),  -- -0.05080560
    to_signed(0, 16),  -- 0.00000000
    to_signed(6025, 16),  -- 0.18387171
    to_signed(12124, 16),  -- 0.36999483
    to_signed(12124, 16),  -- 0.36999483
    to_signed(6025, 16),  -- 0.18387171
    to_signed(0, 16),  -- 0.00000000
    to_signed(-1665, 16),  -- -0.05080560
    to_signed(-541, 16),  -- -0.01652200
    to_signed(259, 16),  -- 0.00788956
    to_signed(183, 16),  -- 0.00557150
    to_signed(0, 16)  -- 0.00000000
  );


  type t_delay_array is array (0 to g_TAPS-1) of signed(g_DATA_WIDTH-1 downto 0);

  signal s_delay_line : t_delay_array := (others => (others => '0'));
  signal s_acc : signed(g_ACC_WIDTH-1 downto 0) := (others => '0');
begin

  process(i_clk, i_rst)
    variable sum : signed(g_ACC_WIDTH-1 downto 0);
  begin
    if i_rst = '1' then
      s_delay_line <= (others => (others => '0'));
      s_acc        <= (others => '0');
    elsif rising_edge(i_clk) then
      if i_ce = '1' then
        -- unit-delay chain
        s_delay_line(0) <= i_din;
        for i in 1 to g_TAPS-1 loop
          s_delay_line(i) <= s_delay_line(i-1);
        end loop;

        -- multiply-accumulate
        sum := (others => '0');
        for i in 0 to g_TAPS-1 loop
          sum := sum + resize(s_delay_line(i) * c_COEFFS(i), g_ACC_WIDTH);
        end loop;
        s_acc <= sum;
      end if;
    end if;
  end process;
  o_dout <= s_acc;

end architecture rtl;