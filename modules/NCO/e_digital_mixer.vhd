library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.math_real.all;

entity e_digital_mixer is
  generic (
    g_DATA_WIDTH : positive := 16;
    g_PHASE_WIDTH : positive := 32;
    g_LUT_DEPTH : positive := 10
  );
  port (
    i_clk : in std_logic;
    i_rst : in std_logic;
    i_ce : in std_logic;
    i_xin_re : in signed(g_DATA_WIDTH-1 downto 0);
    i_xin_im : in signed(g_DATA_WIDTH-1 downto 0);
    i_freq_word : in unsigned(g_PHASE_WIDTH-1 downto 0);
    o_xout_re : out signed(2*g_DATA_WIDTH downto 0);
    o_xout_im : out signed(2*g_DATA_WIDTH downto 0)
  );
end entity e_digital_mixer;

architecture rtl of e_digital_mixer is

  type lut_t is array (0 to 2**g_LUT_DEPTH-1) of signed(g_DATA_WIDTH-1 downto 0);
  function f_init_sine return lut_t is
    variable l : lut_t;
    variable angle : real;
  begin
    for i in 0 to 2**g_LUT_DEPTH-1 loop
      angle := real(i) * MATH_PI * 2.0 / real(2**g_LUT_DEPTH);
      l(i) := to_signed(integer(sin(angle) * (2.0**(g_DATA_WIDTH-1)-1.0)), g_DATA_WIDTH);
    end loop;
    return l;
  end function;
  constant c_SINE_LUT : lut_t := f_init_sine;

  signal s_phase_acc : unsigned(g_PHASE_WIDTH-1 downto 0) := (others => '0');
  signal s_phase : unsigned(g_PHASE_WIDTH-1 downto 0) := (others => '0');
  signal s_addr : unsigned(g_LUT_DEPTH-1 downto 0) := (others => '0');
  signal s_nco_sin : signed(g_DATA_WIDTH-1 downto 0) := (others => '0');
  signal s_nco_cos : signed(g_DATA_WIDTH-1 downto 0) := (others => '0');
  signal s_mul_re : signed(2*g_DATA_WIDTH downto 0) := (others => '0');
  signal s_mul_im : signed(2*g_DATA_WIDTH downto 0) := (others => '0');
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

  s_phase   <= s_phase_acc;
  s_addr    <= s_phase(g_PHASE_WIDTH-1 downto g_PHASE_WIDTH-g_LUT_DEPTH);
  s_nco_sin <= c_SINE_LUT(to_integer(s_addr));
  s_nco_cos <= c_SINE_LUT(to_integer(s_addr + 2**(g_LUT_DEPTH-2)));

  process(i_clk, i_rst)
  begin
    if i_rst = '1' then
      s_mul_re <= (others => '0');
      s_mul_im <= (others => '0');
    elsif rising_edge(i_clk) then
      if i_ce = '1' then
        s_mul_re <= resize(i_xin_re * s_nco_cos + i_xin_im * s_nco_sin, 2*g_DATA_WIDTH+1);
        s_mul_im <= resize(i_xin_im * s_nco_cos - i_xin_re * s_nco_sin, 2*g_DATA_WIDTH+1);
      end if;
    end if;
  end process;

  o_xout_re <= s_mul_re;
  o_xout_im <= s_mul_im;

end architecture rtl;