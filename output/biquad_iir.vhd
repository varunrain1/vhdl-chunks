library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.math_real.all;

entity biquad_iir is
  generic (
    DATA_WIDTH : positive := 16;
    COEFF_WIDTH : positive := 16
  );
  port (
    clk : in std_logic;
    rst : in std_logic;
    ce : in std_logic;
    din : in signed(DATA_WIDTH-1 downto 0);
    dout : out signed(DATA_WIDTH+COEFF_WIDTH downto 0)
  );
end entity biquad_iir;

architecture rtl of biquad_iir is

  -- b = [0.15505103, 0.31010205, 0.15505103]
  -- a = [1.0, -0.62020410, 0.24040821]
  constant B0 : signed(COEFF_WIDTH-1 downto 0) := to_signed(2540, COEFF_WIDTH);
  constant B1 : signed(COEFF_WIDTH-1 downto 0) := to_signed(5081, COEFF_WIDTH);
  constant B2 : signed(COEFF_WIDTH-1 downto 0) := to_signed(2540, COEFF_WIDTH);
  constant A1 : signed(COEFF_WIDTH-1 downto 0) := to_signed(-10161, COEFF_WIDTH);
  constant A2 : signed(COEFF_WIDTH-1 downto 0) := to_signed(3939, COEFF_WIDTH);

  signal w : signed(DATA_WIDTH+COEFF_WIDTH downto 0) := (others => '0');
  signal w1 : signed(DATA_WIDTH+COEFF_WIDTH downto 0) := (others => '0');
  signal w2 : signed(DATA_WIDTH+COEFF_WIDTH downto 0) := (others => '0');
  signal acc : signed(DATA_WIDTH+COEFF_WIDTH downto 0) := (others => '0');
begin

  process(clk, rst)
    variable w_new : signed(DATA_WIDTH+COEFF_WIDTH downto 0);
    variable y     : signed(DATA_WIDTH+COEFF_WIDTH downto 0);
  begin
    if rst = '1' then
      w1  <= (others => '0');
      w2  <= (others => '0');
      acc <= (others => '0');
    elsif rising_edge(clk) then
      if ce = '1' then
        w_new := resize(din, w_new'length)
               - resize(w1 * A1, w_new'length)
               - resize(w2 * A2, w_new'length);

        y := resize(w_new * B0, y'length)
           + resize(w1    * B1, y'length)
           + resize(w2    * B2, y'length);

        w2  <= w1;
        w1  <= w_new;
        acc <= y;
      end if;
    end if;
  end process;
  dout <= acc;

end architecture rtl;