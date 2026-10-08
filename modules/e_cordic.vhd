library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.math_real.all;

entity e_cordic is
  generic (
    g_XY_WIDTH    : positive := 16;
    g_PHASE_WIDTH : positive := 16;
    g_ITERATIONS  : positive := 16
  );
  port (
    i_clk       : in  std_logic;
    i_rst       : in  std_logic;                     -- asynchronous reset
    i_ce        : in  std_logic;
    i_x      : in  signed(g_XY_WIDTH-1 downto 0);
    i_y      : in  signed(g_XY_WIDTH-1 downto 0);
    i_phase  : in  signed(g_PHASE_WIDTH-1 downto 0);
    o_x     : out signed(g_XY_WIDTH-1 downto 0);
    o_y     : out signed(g_XY_WIDTH-1 downto 0);
    o_phase : out signed(g_PHASE_WIDTH-1 downto 0)
  );
end entity;

architecture rtl of e_cordic is
  type t_xy_array is array (0 to g_ITERATIONS) of signed(g_XY_WIDTH-1 downto 0);
  type t_ph_array is array (0 to g_ITERATIONS) of signed(g_PHASE_WIDTH-1 downto 0);

  signal s_x, s_y : t_xy_array;
  signal s_z    : t_ph_array;

  type t_atan_table is array (0 to g_ITERATIONS-1) of signed(g_PHASE_WIDTH-1 downto 0);
  function gen_atan return t_atan_table is
    variable t     : t_atan_table;
    variable angle : real;
  begin
    for i in 0 to g_ITERATIONS-1 loop
      angle := arctan(2.0**(-i));
      t(i)  := to_signed(integer(angle * 2.0**(g_PHASE_WIDTH-1) / MATH_PI), g_PHASE_WIDTH);
    end loop;
    return t;
  end function;
  constant c_ATAN_TABLE : t_atan_table := gen_atan;
begin
  process(i_clk, i_rst)
  begin
    if i_rst = '1' then
      s_x <= (others => (others => '0'));
      s_y <= (others => (others => '0'));
      s_z <= (others => (others => '0'));
    elsif rising_edge(i_clk) then
      if i_ce = '1' then
        s_x(0) <= i_x;
        s_y(0) <= i_y;
        s_z(0) <= i_phase;

        for i in 0 to g_ITERATIONS-1 loop
          if s_z(i)(g_PHASE_WIDTH-1) = '0' then
            s_x(i+1) <= s_x(i) - shift_right(s_y(i), i);
            s_y(i+1) <= s_y(i) + shift_right(s_x(i), i);
            s_z(i+1) <= s_z(i) - c_ATAN_TABLE(i);
          else
            s_x(i+1) <= s_x(i) + shift_right(s_y(i), i);
            s_y(i+1) <= s_y(i) - shift_right(s_x(i), i);
            s_z(i+1) <= s_z(i) + c_ATAN_TABLE(i);
          end if;
        end loop;
      end if;
    end if;
  end process;

  o_x     <= s_x(g_ITERATIONS);
  o_y     <= s_y(g_ITERATIONS);
  o_phase <= s_z(g_ITERATIONS);
end architecture;