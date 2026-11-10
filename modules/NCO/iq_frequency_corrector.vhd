library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.sine_lut_pkg.all;

entity iq_frequency_corrector is
    generic (
        -- 8.7 MHz at Fs = 122.88 MHz
        -- FTW = round(8.7e6 / 122.88e6 * 2^32)
        G_FTW : unsigned(31 downto 0) := x"12200000"
    );
    port (
        clk       : in  std_logic;
        rst       : in  std_logic;  -- synchronous, active high

        in_valid  : in  std_logic;
        in_i      : in  signed(15 downto 0);
        in_q      : in  signed(15 downto 0);

        out_valid : out std_logic;
        out_i     : out signed(17 downto 0);
        out_q     : out signed(17 downto 0)
    );
end entity;

architecture rtl of iq_frequency_corrector is

    signal phase_acc : unsigned(31 downto 0) := (others => '0');

    signal phase_addr : unsigned(9 downto 0);
    signal cos_addr   : unsigned(9 downto 0);

    -- Synchronous ROM outputs and their matching IQ samples
    signal sine_reg : signed(15 downto 0) := (others => '0');
    signal cos_reg  : signed(15 downto 0) := (others => '0');
    signal i_delay  : signed(15 downto 0) := (others => '0');
    signal q_delay  : signed(15 downto 0) := (others => '0');
    signal valid_delay : std_logic := '0';

    -- Four full-precision signed products: 16 x 16 = 32 bits
    signal prod_ic : signed(31 downto 0) := (others => '0');
    signal prod_qs : signed(31 downto 0) := (others => '0');
    signal prod_qc : signed(31 downto 0) := (others => '0');
    signal prod_is : signed(31 downto 0) := (others => '0');
    signal mixer_valid : std_logic := '0';

begin

    ----------------------------------------------------------------
    -- Phase accumulator. It advances only when an input sample
    -- is accepted. Thus phase remains aligned across valid bubbles.
    ----------------------------------------------------------------
    process(clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                phase_acc <= (others => '0');
            elsif in_valid = '1' then
                phase_acc <= phase_acc + G_FTW;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------
    -- LUT addressing.
    -- One 1024-entry sine table is read at two addresses:
    -- cos(theta) = sin(theta + 90 degrees).
    -- 90 degrees corresponds to 256 addresses.
    ----------------------------------------------------------------
    phase_addr <= phase_acc(31 downto 22);
    cos_addr   <= phase_addr + to_unsigned(256, 10);

    ----------------------------------------------------------------
    -- Synchronous dual-read ROM plus IQ alignment.
    -- The constant table is in sine_lut_pkg.vhd.
    ----------------------------------------------------------------
    process(clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                sine_reg   <= (others => '0');
                cos_reg    <= (others => '0');
                i_delay    <= (others => '0');
                q_delay    <= (others => '0');
                valid_delay <= '0';
            else
                valid_delay <= in_valid;

                if in_valid = '1' then
                    sine_reg <= SINE_LUT(to_integer(phase_addr));
                    cos_reg  <= SINE_LUT(to_integer(cos_addr));

                    i_delay <= in_i;
                    q_delay <= in_q;
                end if;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------
    -- Complex multiplication by exp(-j*theta):
    --
    -- Iout = I*cos(theta) + Q*sin(theta)
    -- Qout = Q*cos(theta) - I*sin(theta)
    --
    -- LUT values are signed Q1.15.
    ----------------------------------------------------------------
    process(clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                prod_ic <= (others => '0');
                prod_qs <= (others => '0');
                prod_qc <= (others => '0');
                prod_is <= (others => '0');
                mixer_valid <= '0';
            else
                mixer_valid <= valid_delay;

                if valid_delay = '1' then
                    prod_ic <= i_delay * cos_reg;
                    prod_qs <= q_delay * sine_reg;
                    prod_qc <= q_delay * cos_reg;
                    prod_is <= i_delay * sine_reg;
                end if;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------
    -- Sum products, restore Q1.15 scale, and register output.
    -- 33-bit sums avoid overflow before scaling.
    -- The final 18-bit result has ample headroom for a 16-bit
    -- complex input undergoing a unit-magnitude rotation.
    ----------------------------------------------------------------
    process(clk)
        variable acc_i : signed(32 downto 0);
        variable acc_q : signed(32 downto 0);
        variable scaled_i : signed(32 downto 0);
        variable scaled_q : signed(32 downto 0);
    begin
        if rising_edge(clk) then
            if rst = '1' then
                out_i <= (others => '0');
                out_q <= (others => '0');
                out_valid <= '0';
            else
                out_valid <= mixer_valid;

                if mixer_valid = '1' then
                    acc_i := resize(prod_ic, 33) + resize(prod_qs, 33);
                    acc_q := resize(prod_qc, 33) - resize(prod_is, 33);

                    -- Arithmetic shift right by 15 removes Q1.15 scaling.
                    scaled_i := shift_right(acc_i, 15);
                    scaled_q := shift_right(acc_q, 15);

                    out_i <= resize(scaled_i, 18);
                    out_q <= resize(scaled_q, 18);
                end if;
            end if;
        end if;
    end process;

end architecture;
