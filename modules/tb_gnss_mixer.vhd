
library ieee;
use ieee.std_logic_1164.all;
use ieee.math_real.all;

entity tb_gnss_mixer is
end entity;

architecture sim of tb_gnss_mixer is

    constant CLK_PERIOD : time := 8.138020833 ns;

    constant FS : real := 122.88e6;
    constant FC : real := 8.7e6;

    constant AMPLITUDE : real := 12000.0;

    signal clk : std_logic := '0';
    signal rst : std_logic := '1';

    signal i_in  : integer := 0;
    signal q_in  : integer := 0;

    signal i_out : integer;
    signal q_out : integer;

begin

    -- Clock generation
    clk <= not clk after CLK_PERIOD / 2;

    -- DUT
    DUT : entity work.gnss_mixer
        port map (
            clk   => clk,
            rst   => rst,
            i_in  => i_in,
            q_in  => q_in,
            i_out => i_out,
            q_out => q_out
        );

    -- Stimulus and checking
    stimulus : process

        variable sample_no : integer := 0;
        variable angle     : real;

        variable max_i_error : integer := 0;
        variable max_q_error : integer := 0;

        variable error_i : integer;
        variable error_q : integer;

    begin

        -- Reset
        rst <= '1';
        wait for 5 * CLK_PERIOD;

        wait until falling_edge(clk);
        rst <= '0';

        -- Generate 1000 ADC samples
        for n in 0 to 999 loop

            sample_no := n;

            -- Generate downconverted I/Q signal
            angle := 2.0 * MATH_PI *
                     FC * real(sample_no) / FS;

            i_in <= integer(
                AMPLITUDE * cos(angle)
            );

            q_in <= integer(
                AMPLITUDE * sin(angle)
            );

            -- DUT samples inputs at next rising edge
            wait until rising_edge(clk);
            wait for 1 ns;

            -- Compare against expected DC output
            error_i := abs(i_out - 12000);
            error_q := abs(q_out);

            if error_i > max_i_error then
                max_i_error := error_i;
            end if;

            if error_q > max_q_error then
                max_q_error := error_q;
            end if;

        end loop;

        -- Report results
        report "Simulation completed.";

        report "Maximum I error = " &
               integer'image(max_i_error);

        report "Maximum Q error = " &
               integer'image(max_q_error);

        -- Allow small numerical quantization errors
        assert max_i_error <= 5
            report "FAIL: I output is not constant!"
            severity failure;

        assert max_q_error <= 5
            report "FAIL: Q output contains residual rotation!"
            severity failure;

        report "PASS: 8.7 MHz residual successfully removed!"
            severity note;

        wait;

    end process;

end architecture;
