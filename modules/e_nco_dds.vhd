library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.math_real.all;

entity e_nco_dds is
  generic (
    g_PHASE_WIDTH : positive := 32;
    g_DATA_WIDTH  : positive := 16;
    g_LUT_DEPTH   : positive := 10
  );
  port (
    i_clk       : in  std_logic;
    i_rst       : in  std_logic;                     -- asynchronous reset
    i_ce        : in  std_logic;
    i_freq_word : in  unsigned(g_PHASE_WIDTH-1 downto 0);
    i_phase_mod : in  signed(g_PHASE_WIDTH-1 downto 0) := (others => '0');
    o_sine      : out signed(g_DATA_WIDTH-1 downto 0);
    o_cosine    : out signed(g_DATA_WIDTH-1 downto 0)
  );
end entity;

architecture rtl of e_nco_dds is
  signal s_phase_acc : unsigned(g_PHASE_WIDTH-1 downto 0) := (others => '0');
  signal s_phase     : unsigned(g_PHASE_WIDTH-1 downto 0);

  type t_lut is array (0 to 2**g_LUT_DEPTH-1) of signed(g_DATA_WIDTH-1 downto 0);
  function init_sine return t_lut is
    variable l     : t_lut;
    variable angle : real;
  begin
    for i in 0 to 2**g_LUT_DEPTH-1 loop
      angle := real(i) * MATH_PI * 2.0 / real(2**g_LUT_DEPTH);
      l(i)  := to_signed(integer(sin(angle) * (2.0**(g_DATA_WIDTH-1)-1.0)), g_DATA_WIDTH);
    end loop;
    return l;
  end function;
  constant c_SINE_LUT : t_lut := init_sine;

  signal s_addr : unsigned(g_LUT_DEPTH-1 downto 0);
begin
  process(i_clk, i_rst)
  begin
    if i_rst = '1' then
      s_phase_acc <= (others => '0');
    elsif rising_edge(i_clk) then
      if i_ce = '1' then
        s_phase_acc <= s_phase_acc + i_freq_word;
      end if;
    end if;
  end process;

  s_phase <= s_phase_acc + unsigned(i_phase_mod);
  s_addr  <= s_phase(g_PHASE_WIDTH-1 downto g_PHASE_WIDTH-g_LUT_DEPTH);

  o_sine   <= c_SINE_LUT(to_integer(s_addr));
  o_cosine <= c_SINE_LUT(to_integer(s_addr + 2**(g_LUT_DEPTH-2)));
end architecture;